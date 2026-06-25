from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"           # 심사 대기
    APPROVED = "APPROVED"         # 승인 가능
    CONDITIONAL = "CONDITIONAL"   # 조건부 승인
    REVIEW = "REVIEW"             # 검토 필요
    REJECTED = "REJECTED"         # 부적합


class InputMethod(str, enum.Enum):
    MANUAL = "MANUAL"
    EXCEL = "EXCEL"
    PDF = "PDF"


class ProfitSheetHeader(Base):
    __tablename__ = "profit_sheet_header"

    id = Column(Integer, primary_key=True, index=True)
    case_no = Column(String(100), unique=True, index=True)  # 안건번호
    job_code = Column(String(20), nullable=False)           # SE, SI+, AE++ 등
    customer_id = Column(Integer, ForeignKey("customer_master.id"))
    customer_name = Column(String(200))
    customer_type = Column(String(20))                      # SHIPPER, FORWARDER, PARTNER
    partner_id = Column(Integer, ForeignKey("partner_master.id"), nullable=True)
    partner_name = Column(String(200))
    assignee_id = Column(Integer, ForeignKey("users.id"))
    assignee_name = Column(String(100))
    zone = Column(String(100))                              # 업무 Zone
    origin_port = Column(String(100))
    dest_port = Column(String(100))
    etd = Column(DateTime(timezone=True))                   # 출항일
    eta = Column(DateTime(timezone=True))                   # 도착일
    weight_kg = Column(Float)
    cbm = Column(Float)
    rt = Column(Float)                                      # RT (RT 로직 자동 계산)
    container_type = Column(String(50))                     # 20GP, 40GP, 40HC, LCL 등
    base_currency = Column(String(10), default="JPY")
    exchange_rate_usd = Column(Float)
    exchange_rate_krw = Column(Float)
    total_revenue_jpy = Column(Float)                       # 총 매출 (엔 기준)
    total_cost_jpy = Column(Float)                          # 총 매입 (엔 기준)
    gp_jpy = Column(Float)                                  # GP (엔)
    gp_rate = Column(Float)                                 # GP율 (%)
    point = Column(Float)                                   # 생산성 포인트
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    input_method = Column(Enum(InputMethod), default=InputMethod.MANUAL)
    original_file_path = Column(String(500))
    notes = Column(Text)
    # ── 인간 결재 ──────────────────────────────────────────────
    human_decision = Column(String(20), nullable=True)       # APPROVED / REJECTED / null
    human_comment  = Column(Text, nullable=True)             # 결재 의견
    human_decided_by = Column(String(100), nullable=True)    # 결재자 이름
    human_decided_at = Column(DateTime(timezone=True), nullable=True)  # 결재 일시
    # ── 계약 시점 환율 ─────────────────────────────────────────
    exchange_rate_note = Column(String(200), nullable=True)  # 환율 출처/기준일시 메모
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    details = relationship("ProfitSheetDetail", back_populates="header")


class ProfitSheetDetail(Base):
    __tablename__ = "profit_sheet_detail"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("profit_sheet_header.id"), nullable=False)
    charge_code = Column(String(50), nullable=False)     # OF, THC, BAF 등
    charge_name = Column(String(200))
    is_revenue = Column(Boolean, nullable=False)          # True=매출, False=매입
    currency = Column(String(10), default="JPY")
    amount = Column(Float, nullable=False)
    amount_jpy = Column(Float)                            # 엔 환산 금액
    partner_name = Column(String(200))                    # 매입처 (매입 항목인 경우)
    quantity = Column(Float, default=1.0)
    unit = Column(String(50))
    is_missing_flag = Column(Boolean, default=False)      # 비용 누락 의심 플래그
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    header = relationship("ProfitSheetHeader", back_populates="details")
