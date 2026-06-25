from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ProfitSheetDetailCreate(BaseModel):
    charge_code: str
    charge_name: Optional[str] = None
    is_revenue: bool
    currency: str = "JPY"
    amount: float
    amount_jpy: Optional[float] = None
    partner_name: Optional[str] = None
    quantity: float = 1.0
    unit: Optional[str] = None
    notes: Optional[str] = None


class ProfitSheetCreate(BaseModel):
    case_no: Optional[str] = None
    job_code: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_type: Optional[str] = None
    partner_id: Optional[int] = None
    partner_name: Optional[str] = None
    zone: Optional[str] = None
    origin_port: Optional[str] = None
    dest_port: Optional[str] = None
    etd: Optional[datetime] = None
    eta: Optional[datetime] = None
    weight_kg: Optional[float] = None
    cbm: Optional[float] = None
    container_type: Optional[str] = None
    base_currency: str = "JPY"
    exchange_rate_usd: Optional[float] = None
    exchange_rate_krw: Optional[float] = None
    notes: Optional[str] = None
    details: List[ProfitSheetDetailCreate] = []


class ProfitSheetDetailOut(ProfitSheetDetailCreate):
    id: int
    is_missing_flag: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProfitSheetOut(BaseModel):
    id: int
    case_no: Optional[str]
    job_code: str
    customer_name: Optional[str]
    customer_type: Optional[str]
    partner_name: Optional[str]
    assignee_name: Optional[str]
    zone: Optional[str]
    origin_port: Optional[str]
    dest_port: Optional[str]
    etd: Optional[datetime]
    eta: Optional[datetime]
    weight_kg: Optional[float]
    cbm: Optional[float]
    rt: Optional[float]
    container_type: Optional[str]
    base_currency: str
    exchange_rate_usd: Optional[float]
    exchange_rate_krw: Optional[float]
    exchange_rate_note: Optional[str]
    total_revenue_jpy: Optional[float]
    total_cost_jpy: Optional[float]
    gp_jpy: Optional[float]
    gp_rate: Optional[float]
    point: Optional[float]
    status: str
    input_method: str
    notes: Optional[str]
    # 인간 결재
    human_decision: Optional[str]
    human_comment: Optional[str]
    human_decided_by: Optional[str]
    human_decided_at: Optional[datetime]
    created_at: datetime
    details: List[ProfitSheetDetailOut] = []

    class Config:
        from_attributes = True


class ProfitSheetListItem(BaseModel):
    id: int
    case_no: Optional[str]
    job_code: str
    customer_name: Optional[str]
    customer_type: Optional[str]
    assignee_name: Optional[str]
    origin_port: Optional[str]
    dest_port: Optional[str]
    total_revenue_jpy: Optional[float]
    gp_jpy: Optional[float]
    gp_rate: Optional[float]
    exchange_rate_usd: Optional[float]
    exchange_rate_krw: Optional[float]
    status: str
    # 인간 결재
    human_decision: Optional[str]
    human_comment: Optional[str]
    human_decided_by: Optional[str]
    human_decided_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
