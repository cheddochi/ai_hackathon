from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CustomerCreate(BaseModel):
    code: str
    name: str
    name_en: Optional[str] = None
    customer_type: str  # SHIPPER, FORWARDER, PARTNER
    country: Optional[str] = None
    contact: Optional[str] = None


class CustomerOut(CustomerCreate):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PartnerCreate(BaseModel):
    code: str
    name: str
    name_en: Optional[str] = None
    partner_type: Optional[str] = None
    country: Optional[str] = None
    max_fee_per_case: Optional[float] = None
    max_fee_rate: Optional[float] = None


class PartnerOut(PartnerCreate):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GpRuleCreate(BaseModel):
    rule_name: str
    rule_type: str
    job_code: Optional[str] = None
    customer_type: Optional[str] = None
    revenue_min_jpy: Optional[float] = None
    revenue_max_jpy: Optional[float] = None
    min_gp_jpy: Optional[float] = None
    min_gp_rate: Optional[float] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class GpRuleOut(GpRuleCreate):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ExchangeRateCreate(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    effective_date: datetime


class ExchangeRateOut(ExchangeRateCreate):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JobCodeOut(BaseModel):
    id: int
    code: str
    description: str
    transport_type: Optional[str]
    includes_customs: bool
    includes_transport: bool
    includes_warehouse: bool
    point: float
    is_active: bool

    class Config:
        from_attributes = True
