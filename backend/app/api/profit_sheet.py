import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.api.auth import get_current_user
from app.models.user import User
from app.models.transaction import ProfitSheetHeader, ProfitSheetDetail, InputMethod, ApprovalStatus
from app.models.master import JobCodeMaster
from app.schemas.transaction import ProfitSheetCreate, ProfitSheetOut, ProfitSheetListItem
from app.services.pdf_parser import parse_pdf, ParsedProfitSheet
from app.services.excel_parser import parse_excel
from app.services.approval_engine import calculate_rt
from app.services.ai_analyzer import analyze_transaction

router = APIRouter(prefix="/profit-sheets", tags=["profit-sheet"])


# ─── 내부 유틸 ───────────────────────────────────────────────

def _calc_gp(header: ProfitSheetHeader) -> None:
    header.rt = calculate_rt(header.weight_kg, header.cbm)
    header.gp_jpy = (header.total_revenue_jpy or 0) - (header.total_cost_jpy or 0)
    if header.total_revenue_jpy and header.total_revenue_jpy > 0:
        header.gp_rate = header.gp_jpy / header.total_revenue_jpy * 100
    else:
        header.gp_rate = 0.0


def _get_exchange_rate(currency: str, header: ProfitSheetHeader) -> float:
    if currency == "JPY":
        return 1.0
    elif currency == "USD":
        return header.exchange_rate_usd or 150.0
    elif currency == "KRW":
        return 1 / (header.exchange_rate_krw or 9.5)
    return 1.0


def _process_details(header: ProfitSheetHeader, details_data: list, db: Session) -> None:
    total_rev, total_cost = 0.0, 0.0
    for d in details_data:
        rate = _get_exchange_rate(d.currency, header)
        amount_jpy = d.amount * rate
        detail = ProfitSheetDetail(
            header_id=header.id,
            charge_code=d.charge_code,
            charge_name=d.charge_name,
            is_revenue=d.is_revenue,
            currency=d.currency,
            amount=d.amount,
            amount_jpy=amount_jpy,
            partner_name=d.partner_name,
            quantity=getattr(d, 'quantity', 1.0),
            unit=getattr(d, 'unit', None),
            notes=getattr(d, 'notes', None),
        )
        db.add(detail)
        if d.is_revenue:
            total_rev += amount_jpy
        else:
            total_cost += amount_jpy

    header.total_revenue_jpy = total_rev
    header.total_cost_jpy = total_cost
    _calc_gp(header)

    job = db.query(JobCodeMaster).filter(JobCodeMaster.code == header.job_code).first()
    header.point = job.point if job else 1.0


def _parse_date(date_str: str):
    """날짜 문자열 → datetime or None"""
    if not date_str:
        return None
    import re
    from datetime import datetime
    # 형식: 2026-05-03 or 2026/05/03
    m = re.match(r'(\d{4})[-/](\d{2})[-/](\d{2})', date_str.strip())
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _header_from_parsed(
    parsed: ParsedProfitSheet,
    current_user: User,
    file_path: str,
) -> ProfitSheetHeader:
    """ParsedProfitSheet → ProfitSheetHeader 매핑"""
    # 메타 정보를 notes JSON에 저장
    notes_data: dict = {}
    if parsed.mbl_no:
        notes_data['mbl_no'] = parsed.mbl_no
    if parsed.ref_no:
        notes_data['ref_no'] = parsed.ref_no
    if parsed.vessel_voy:
        notes_data['vessel_voy'] = parsed.vessel_voy
    if parsed.cntr_info:
        notes_data['cntr_info'] = parsed.cntr_info
    if parsed.profit_usd:
        notes_data['profit_usd'] = parsed.profit_usd
    if parsed.profit_tot_jpy:
        notes_data['profit_tot_jpy'] = parsed.profit_tot_jpy
    notes_data['is_ocr'] = parsed.is_ocr
    notes_data['parse_confidence'] = parsed.confidence
    if parsed.parse_warnings:
        notes_data['warnings'] = parsed.parse_warnings

    return ProfitSheetHeader(
        case_no=parsed.hbl_no or parsed.ref_no or f"PDF-{uuid.uuid4().hex[:8].upper()}",
        job_code=parsed.job_code or "SE",
        customer_name=parsed.customer_name,
        partner_name=parsed.partner,
        assignee_id=current_user.id,
        assignee_name=current_user.name,
        origin_port=parsed.pol,
        dest_port=parsed.pod,
        etd=_parse_date(parsed.etd),
        eta=_parse_date(parsed.eta),
        weight_kg=parsed.weight_kg,
        cbm=parsed.cbm,
        rt=parsed.r_ton,
        container_type=parsed.cntr_info,
        base_currency="JPY",
        exchange_rate_usd=parsed.ex_rate_usd or None,
        input_method=InputMethod.PDF,
        original_file_path=file_path,
        status=ApprovalStatus.PENDING,
        notes=json.dumps(notes_data, ensure_ascii=False) if notes_data else None,
    )


def _save_upload(file: UploadFile) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(
        settings.UPLOAD_DIR,
        f"{uuid.uuid4().hex}_{file.filename}",
    )
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return file_path


# ─── Routes ──────────────────────────────────────────────────

@router.post("", response_model=ProfitSheetOut)
def create_profit_sheet(
    data: ProfitSheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    header = ProfitSheetHeader(
        case_no=data.case_no or f"CASE-{uuid.uuid4().hex[:8].upper()}",
        job_code=data.job_code,
        customer_id=data.customer_id,
        customer_name=data.customer_name,
        customer_type=data.customer_type,
        partner_id=data.partner_id,
        partner_name=data.partner_name,
        assignee_id=current_user.id,
        assignee_name=current_user.name,
        zone=data.zone,
        origin_port=data.origin_port,
        dest_port=data.dest_port,
        etd=data.etd,
        eta=data.eta,
        weight_kg=data.weight_kg,
        cbm=data.cbm,
        container_type=data.container_type,
        base_currency=data.base_currency,
        exchange_rate_usd=data.exchange_rate_usd,
        exchange_rate_krw=data.exchange_rate_krw,
        notes=data.notes,
        input_method=InputMethod.MANUAL,
        status=ApprovalStatus.PENDING,
    )
    db.add(header)
    db.flush()
    _process_details(header, data.details, db)
    db.commit()
    db.refresh(header)
    return header


@router.post("/upload/pdf", response_model=ProfitSheetOut)
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")

    file_path = _save_upload(file)
    parsed = parse_pdf(file_path)

    from app.schemas.transaction import ProfitSheetDetailCreate
    header = _header_from_parsed(parsed, current_user, file_path)

    # AI 거래 분석 (ANTHROPIC_API_KEY 있을 때만 동작, 실패해도 업로드 계속)
    if parsed.raw_text:
        header.ai_analysis = analyze_transaction(parsed.raw_text, parsed.hbl_no)

    db.add(header)
    db.flush()

    detail_creates = [
        ProfitSheetDetailCreate(
            charge_code=c.charge_code,
            charge_name=c.charge_name,
            is_revenue=c.is_revenue,
            currency=c.currency,
            amount=c.amount if c.currency != "JPY" else c.amount_jpy,
            partner_name=c.account_name,
        )
        for c in parsed.charges
    ]
    _process_details(header, detail_creates, db)
    db.commit()
    db.refresh(header)
    return header


@router.post("/upload/pdf/bulk")
async def upload_pdf_bulk(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    복수 PDF 업로드
    반환: 파일별 결과 목록 [{filename, hbl_no, sheet_id, status, warnings}]
    — 개별 파일 오류는 결과 목록에 포함, 전체 실패 방지
    """
    import logging as _log
    _logger = _log.getLogger(__name__)
    results = []

    for file in files:
        item: dict = {
            "filename": file.filename,
            "hbl_no": "",
            "sheet_id": None,
            "status": "error",
            "warnings": [],
        }

        if not file.filename.lower().endswith(".pdf"):
            item["warnings"].append("PDF 파일이 아닙니다")
            results.append(item)
            continue

        file_path = None
        try:
            # ── 파일 저장 ──────────────────────────────────────
            file_path = _save_upload(file)

            # ── PDF 파싱 (OCR 포함) ────────────────────────────
            parsed = parse_pdf(file_path)
            item["hbl_no"]   = parsed.hbl_no
            item["warnings"] = list(parsed.parse_warnings)  # 복사본

            # ── 중복 체크 ──────────────────────────────────────
            case_no = parsed.hbl_no or parsed.ref_no
            if case_no:
                existing = db.query(ProfitSheetHeader).filter(
                    ProfitSheetHeader.case_no == case_no
                ).first()
                if existing:
                    item["status"]   = "duplicate"
                    item["sheet_id"] = existing.id
                    item["warnings"].append(f"이미 등록된 H.B/L NO (ID: {existing.id})")
                    results.append(item)
                    continue

            # ── DB 저장 ────────────────────────────────────────
            from app.schemas.transaction import ProfitSheetDetailCreate
            header = _header_from_parsed(parsed, current_user, file_path)

            # AI 거래 분석
            if parsed.raw_text:
                header.ai_analysis = analyze_transaction(parsed.raw_text, parsed.hbl_no)

            db.add(header)
            db.flush()

            detail_creates = [
                ProfitSheetDetailCreate(
                    charge_code=c.charge_code,
                    charge_name=c.charge_name,
                    is_revenue=c.is_revenue,
                    currency=c.currency,
                    amount=c.amount if c.currency != "JPY" else c.amount_jpy,
                    partner_name=c.account_name,
                )
                for c in parsed.charges
            ]
            _process_details(header, detail_creates, db)
            db.commit()
            db.refresh(header)

            item["sheet_id"] = header.id
            item["status"]   = "success"

        except Exception as exc:
            _logger.error(f"[bulk] {file.filename} 처리 오류: {exc}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            item["warnings"].append(f"처리 오류: {type(exc).__name__}: {str(exc)[:200]}")
            item["status"] = "error"

        results.append(item)

    return {"total": len(results), "results": results}


@router.post("/upload/excel", response_model=ProfitSheetOut)
async def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")

    file_path = _save_upload(file)
    parsed = parse_excel(file_path)

    header = ProfitSheetHeader(
        case_no=parsed.case_no or f"XLS-{uuid.uuid4().hex[:8].upper()}",
        job_code=parsed.job_code or "SE",
        customer_name=parsed.customer_name,
        assignee_id=current_user.id,
        assignee_name=current_user.name,
        origin_port=parsed.origin_port,
        dest_port=parsed.dest_port,
        weight_kg=parsed.weight_kg,
        cbm=parsed.cbm,
        input_method=InputMethod.EXCEL,
        original_file_path=file_path,
        status=ApprovalStatus.PENDING,
        notes="; ".join(parsed.parse_warnings) if parsed.parse_warnings else None,
    )
    db.add(header)
    db.flush()

    from app.schemas.transaction import ProfitSheetDetailCreate
    detail_creates = [
        ProfitSheetDetailCreate(
            charge_code=c.charge_code,
            charge_name=c.charge_name,
            is_revenue=c.is_revenue,
            currency=c.currency,
            amount=c.amount,
            partner_name=c.partner_name,
        )
        for c in parsed.charges
    ]
    _process_details(header, detail_creates, db)
    db.commit()
    db.refresh(header)
    return header


@router.get("", response_model=List[ProfitSheetListItem])
def list_profit_sheets(
    status: Optional[str] = None,
    job_code: Optional[str] = None,
    customer_name: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ProfitSheetHeader)
    if status:
        q = q.filter(ProfitSheetHeader.status == status)
    if job_code:
        q = q.filter(ProfitSheetHeader.job_code.ilike(f"{job_code}%"))
    if customer_name:
        q = q.filter(ProfitSheetHeader.customer_name.ilike(f"%{customer_name}%"))
    return q.order_by(ProfitSheetHeader.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{sheet_id}", response_model=ProfitSheetOut)
def get_profit_sheet(
    sheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sheet = db.query(ProfitSheetHeader).filter(ProfitSheetHeader.id == sheet_id).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Not found")
    return sheet


@router.delete("/{sheet_id}")
def delete_profit_sheet(
    sheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sheet = db.query(ProfitSheetHeader).filter(ProfitSheetHeader.id == sheet_id).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Not found")
    db.query(ProfitSheetDetail).filter(ProfitSheetDetail.header_id == sheet_id).delete()
    db.delete(sheet)
    db.commit()
    return {"ok": True}


# ── 인간 결재 ─────────────────────────────────────────────────

class DecisionRequest(BaseModel):
    decision: Optional[str] = None          # "APPROVED" | "REJECTED" | null(해제)
    comment: Optional[str] = None           # 결재 의견
    exchange_rate_krw: Optional[float] = None   # JPY→KRW 환율
    exchange_rate_usd: Optional[float] = None   # USD→JPY 환율
    exchange_rate_note: Optional[str] = None    # 환율 출처/기준일시 메모


@router.patch("/{sheet_id}/decision", response_model=ProfitSheetOut)
def update_decision(
    sheet_id: int,
    body: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    인간 결재 — 승인 / 반려 / 해제 (decision=null)
    환율도 함께 저장하여 계약 시점 기준환율을 보존합니다.
    """
    sheet = db.query(ProfitSheetHeader).filter(ProfitSheetHeader.id == sheet_id).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Not found")

    # 결재값 검증
    if body.decision is not None and body.decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="decision은 APPROVED / REJECTED / null 만 허용됩니다")

    # 인간 결재 저장
    sheet.human_decision = body.decision
    sheet.human_comment  = body.comment
    if body.decision is not None:
        sheet.human_decided_by = current_user.name
        sheet.human_decided_at = datetime.now(timezone.utc)
    else:
        # 해제 시 결재자/일시도 초기화
        sheet.human_decided_by = None
        sheet.human_decided_at = None

    # 환율 저장 (값이 있을 때만 덮어쓰기)
    if body.exchange_rate_krw is not None:
        sheet.exchange_rate_krw = body.exchange_rate_krw
    if body.exchange_rate_usd is not None:
        sheet.exchange_rate_usd = body.exchange_rate_usd
    if body.exchange_rate_note is not None:
        sheet.exchange_rate_note = body.exchange_rate_note

    # 환율이 변경된 경우 KRW 환산 금액 재계산
    if body.exchange_rate_krw is not None or body.exchange_rate_usd is not None:
        _recalc_krw(sheet, db)

    db.commit()
    db.refresh(sheet)
    return sheet


def _recalc_krw(sheet: ProfitSheetHeader, db: Session) -> None:
    """환율 변경 시 detail의 amount_jpy 기반으로 합계를 재계산 (JPY 기준 변경 없음, 환율 메타만 저장)."""
    # 현재 설계에서 amount_jpy는 JPY 기준으로 고정되어 있으므로
    # KRW 환산은 프론트엔드에서 exchange_rate_krw 를 곱해서 표시합니다.
    # 여기서는 exchange_rate_krw 값 저장만 처리합니다 (향후 amount_krw 컬럼 추가 시 확장).
    pass
