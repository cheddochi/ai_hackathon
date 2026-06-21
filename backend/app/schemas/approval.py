from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class RuleResultOut(BaseModel):
    rule_code: str
    rule_name: str
    passed: bool
    input_value: str
    threshold_value: str
    message: str


class ApprovalOut(BaseModel):
    id: int
    header_id: int
    judgment: str
    gp_rule_passed: Optional[bool]
    partner_fee_passed: Optional[bool]
    internal_resource_passed: Optional[bool]
    cost_omission_passed: Optional[bool]
    gp_jpy_snapshot: Optional[float]
    gp_rate_snapshot: Optional[float]
    revenue_snapshot: Optional[float]
    comments: Optional[str]
    created_at: datetime
    rule_logs: List[RuleResultOut] = []

    class Config:
        from_attributes = True


class TodoOut(BaseModel):
    id: int
    header_id: int
    title: str
    description: Optional[str]
    rule_code: Optional[str]
    priority: str
    status: str
    assignee_id: Optional[int]
    due_date: Optional[datetime]
    created_at: datetime
    case_no: Optional[str] = None
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True


class TodoUpdate(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[int] = None
    due_date: Optional[datetime] = None
    description: Optional[str] = None
