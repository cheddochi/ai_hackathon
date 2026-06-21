from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, Text, ForeignKey
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class JudgmentResult(str, enum.Enum):
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"


class TodoPriority(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TodoStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("profit_sheet_header.id"), nullable=False)
    judgment = Column(Enum(JudgmentResult), nullable=False)
    gp_rule_passed = Column(Boolean)
    partner_fee_passed = Column(Boolean)
    internal_resource_passed = Column(Boolean)
    cost_omission_passed = Column(Boolean)
    gp_jpy_snapshot = Column(Float)
    gp_rate_snapshot = Column(Float)
    revenue_snapshot = Column(Float)
    rule_version = Column(String(50))        # 판정 시점의 GP 룰 버전
    exchange_rate_snapshot = Column(String(200))  # JSON 스냅샷
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    comments = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RuleEvaluationLog(Base):
    __tablename__ = "rule_evaluation_log"

    id = Column(Integer, primary_key=True, index=True)
    approval_history_id = Column(Integer, ForeignKey("approval_history.id"), nullable=False)
    rule_code = Column(String(50), nullable=False)    # GP_CHECK, PARTNER_FEE, INTERNAL_RESOURCE, COST_OMISSION
    rule_name = Column(String(200))
    passed = Column(Boolean, nullable=False)
    input_value = Column(String(500))
    threshold_value = Column(String(500))
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Todo(Base):
    __tablename__ = "todo"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("profit_sheet_header.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    rule_code = Column(String(50))           # 어떤 룰에서 생성됐는지
    priority = Column(Enum(TodoPriority), default=TodoPriority.MEDIUM)
    status = Column(Enum(TodoStatus), default=TodoStatus.OPEN)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_date = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ProductivityHistory(Base):
    __tablename__ = "productivity_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    header_id = Column(Integer, ForeignKey("profit_sheet_header.id"), nullable=False)
    job_code = Column(String(20), nullable=False)
    point = Column(Float, nullable=False)
    year_month = Column(String(7), nullable=False)  # "2026-06"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
