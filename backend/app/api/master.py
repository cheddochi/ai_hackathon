import re
import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.auth import get_current_user, require_admin
from app.models.user import User
from app.models.master import Customer, Partner, GpRuleMaster, ExchangeRate, JobCodeMaster
from app.schemas.master import (
    CustomerCreate, CustomerOut,
    PartnerCreate, PartnerOut,
    GpRuleCreate, GpRuleOut,
    ExchangeRateCreate, ExchangeRateOut,
    JobCodeOut,
)

_logger = logging.getLogger(__name__)

SMBS_URL = "http://www.smbs.biz/ExRate/TodayExRate.jsp"

router = APIRouter(prefix="/master", tags=["master"])


# ── 거래처 ──────────────────────────────────────────────────
@router.get("/customers", response_model=List[CustomerOut])
def list_customers(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Customer).filter(Customer.is_active == True).all()


@router.post("/customers", response_model=CustomerOut)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    customer = Customer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


# ── 파트너 ──────────────────────────────────────────────────
@router.get("/partners", response_model=List[PartnerOut])
def list_partners(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Partner).filter(Partner.is_active == True).all()


@router.post("/partners", response_model=PartnerOut)
def create_partner(data: PartnerCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    partner = Partner(**data.model_dump())
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


# ── GP 기준 ─────────────────────────────────────────────────
@router.get("/gp-rules", response_model=List[GpRuleOut])
def list_gp_rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(GpRuleMaster).filter(GpRuleMaster.is_active == True).all()


@router.post("/gp-rules", response_model=GpRuleOut)
def create_gp_rule(data: GpRuleCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rule = GpRuleMaster(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/gp-rules/{rule_id}", response_model=GpRuleOut)
def update_gp_rule(
    rule_id: int,
    data: GpRuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rule = db.query(GpRuleMaster).filter(GpRuleMaster.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in data.model_dump().items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule


# ── 환율 ────────────────────────────────────────────────────
@router.get("/exchange-rates", response_model=List[ExchangeRateOut])
def list_exchange_rates(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(ExchangeRate).filter(ExchangeRate.is_active == True).all()


@router.post("/exchange-rates", response_model=ExchangeRateOut)
def create_exchange_rate(data: ExchangeRateCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rate = ExchangeRate(**data.model_dump())
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate


# ── 업무코드 ─────────────────────────────────────────────────
@router.get("/job-codes", response_model=List[JobCodeOut])
def list_job_codes(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(JobCodeMaster).filter(JobCodeMaster.is_active == True).all()


# ── SMBS 실시간 환율 조회 ────────────────────────────────────
@router.get("/exchange-rate/today")
def get_today_exchange_rate(_: User = Depends(get_current_user)):
    """
    서울외국환중개(SMBS) 사이트에서 오늘의 환율을 조회합니다.
    반환: { usd_krw, jpy_krw, usd_jpy, fetched_at, source }
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(SMBS_URL, headers=headers)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        usd_krw: float | None = None
        jpy_krw: float | None = None

        # SMBS 페이지는 통화명과 환율이 테이블 행에 배치됨
        # USD, JPY 행을 찾아 매매기준율(buying rate) 파싱
        for row in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 3:
                continue
            currency_cell = cells[0].upper()
            # 숫자만 추출 (콤마 제거)
            def _parse_rate(s: str) -> float | None:
                cleaned = re.sub(r"[^\d.]", "", s)
                try:
                    return float(cleaned) if cleaned else None
                except ValueError:
                    return None

            if "USD" in currency_cell or "미국" in currency_cell:
                # 매매기준율은 보통 3번째~4번째 셀
                for c in cells[1:]:
                    v = _parse_rate(c)
                    if v and 900 < v < 2000:  # KRW/USD 합리적 범위
                        usd_krw = v
                        break

            elif "JPY" in currency_cell or "일본" in currency_cell:
                for c in cells[1:]:
                    v = _parse_rate(c)
                    if v and 5 < v < 20:  # KRW/JPY 합리적 범위 (100엔 기준이면 900~1200)
                        jpy_krw = v
                        break
                    # 100엔 기준으로 표기하는 경우
                    if v and 900 < v < 1500:
                        jpy_krw = round(v / 100, 4)
                        break

        fetched_at = datetime.now(timezone.utc).isoformat()

        if usd_krw is None and jpy_krw is None:
            raise ValueError("환율 파싱 실패 — 페이지 구조가 변경되었을 수 있습니다")

        # USD/JPY 교차환율 계산
        usd_jpy: float | None = None
        if usd_krw and jpy_krw and jpy_krw > 0:
            usd_jpy = round(usd_krw / jpy_krw, 2)

        return {
            "usd_krw": usd_krw,
            "jpy_krw": jpy_krw,
            "usd_jpy": usd_jpy,
            "fetched_at": fetched_at,
            "source": "SMBS (서울외국환중개)",
        }

    except httpx.RequestError as e:
        _logger.error(f"SMBS 환율 조회 네트워크 오류: {e}")
        raise HTTPException(status_code=503, detail=f"환율 사이트 접속 실패: {str(e)}")
    except Exception as e:
        _logger.error(f"SMBS 환율 파싱 오류: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"환율 조회 실패: {str(e)}")
