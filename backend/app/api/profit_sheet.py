import os
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.api.auth import get_current_user
from app.models.user import User
from app.models.transaction import ProfitSheetHeader, ProfitSheetDetail, InputMethod, ApprovalStatus
from app.models.master import JobCodeMaster
from app.schemas.transaction import ProfitSheetCreate, ProfitSheetOut, ProfitSheetListItem
from app.services.pdf_parser import parse_pdf
from app.services.excel_parser import parse_excel
from app.services.approval_engine import calculate_rt

router = APIRouter(prefix="/profit-sheets", tags=["profit-sheet"])


def _calc_gp(header: ProfitSheetHeader) -> None:
    """GP, GP율, RT 재계산"""
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
    """상세 항목 저장 및 GP 계산"""
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
            quantity=d.quantity,
            unit=d.unit,
            notes=d.notes,
        )
        db.add(detail)
        if d.is_revenue:
            total_rev += amount_jpy
        else:
            total_cost += amount_jpy

    header.total_revenue_jpy = total_rev
    header.total_cost_jpy = total_cost
    _calc_gp(header)

    # 생산성 포인트 자동 부여
    job = db.query(JobCodeMaster).filter(JobCodeMaster.code == header.job_code).first()
    header.point = job.point if job else 1.0


@router.post("", response_model=ProfitSheetOut)
def create_profit_sheet(
    data: ProfitSheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import re
    case_no = data.case_no or f"CASE-{uuid.uuid4().hex[:8].upper()}"
    header = ProfitSheetHeader(
        case_no=case_no,
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
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    parsed = parse_pdf(file_path)

    header = ProfitSheetHeader(
        case_no=parsed.case_no or f"PDF-{uuid.uuid4().hex[:8].upper()}",
        job_code=parsed.job_code or "SE",
        customer_name=parsed.customer_name,
        assignee_id=current_user.id,
        assignee_name=current_user.name,
        origin_port=parsed.origin_port,
        dest_port=parsed.dest_port,
        weight_kg=parsed.weight_kg,
        cbm=parsed.cbm,
        container_type=parsed.container_type,
        base_currency=parsed.base_currency,
        input_method=InputMethod.PDF,
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


@router.post("/upload/excel", response_model=ProfitSheetOut)
async def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Excel 파일만 업로드 가능합니다")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

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
