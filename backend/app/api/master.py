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
