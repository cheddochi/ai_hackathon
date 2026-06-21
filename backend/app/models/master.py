from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, Text
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class CustomerType(str, enum.Enum):
    SHIPPER = "SHIPPER"
    FORWARDER = "FORWARDER"
    PARTNER = "PARTNER"


class GpRuleType(str, enum.Enum):
    FIXED_AMOUNT = "FIXED_AMOUNT"
    GP_RATE = "GP_RATE"
    HYBRID = "HYBRID"
    BY_CUSTOMER_TYPE = "BY_CUSTOMER_TYPE"


class Customer(Base):
    __tablename__ = "customer_master"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    name_en = Column(String(200))
    customer_type = Column(Enum(CustomerType), nullable=False)
    country = Column(String(100))
    contact = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Partner(Base):
    __tablename__ = "partner_master"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    name_en = Column(String(200))
    partner_type = Column(String(50))  # 운송사, 통관사, 창고업체, 선사, 항공사
    country = Column(String(100))
    max_fee_per_case = Column(Float)  # 건당 최대 허용 Fee (엔)
    max_fee_rate = Column(Float)      # 최대 허용 Fee 비율 (%)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PartnerFeeMaster(Base):
    __tablename__ = "partner_fee_master"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, nullable=False)
    partner_name = Column(String(200), nullable=False)
    job_code = Column(String(20))         # 적용 업무코드 (None이면 전체)
    max_fee_jpy = Column(Float)           # 최대 허용 Fee (엔)
    max_fee_rate = Column(Float)          # 최대 허용 Fee 비율 (%)
    effective_from = Column(DateTime(timezone=True))
    effective_to = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChargeMaster(Base):
    __tablename__ = "charge_master"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name_en = Column(String(200), nullable=False)
    name_ko = Column(String(200))
    category = Column(String(50))  # 해상, 서류, 수출, 수입, 운송, 창고, 항공
    transport_mode = Column(String(20))  # SEA, AIR, ALL
    is_revenue = Column(Boolean, default=True)   # 매출 항목 여부
    is_cost = Column(Boolean, default=True)      # 매입 항목 여부
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobCodeMaster(Base):
    __tablename__ = "job_code_master"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    description = Column(String(200), nullable=False)
    transport_type = Column(String(10))  # SE, SI, AE, AI, PJT
    includes_customs = Column(Boolean, default=False)
    includes_transport = Column(Boolean, default=False)
    includes_warehouse = Column(Boolean, default=False)
    point = Column(Float, nullable=False, default=1.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GpRuleMaster(Base):
    __tablename__ = "gp_rule_master"

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(200), nullable=False)
    rule_type = Column(Enum(GpRuleType), nullable=False)
    job_code = Column(String(20))              # None이면 전체 적용
    customer_type = Column(Enum(CustomerType)) # None이면 전체 적용
    revenue_min_jpy = Column(Float)            # 매출 구간 하한
    revenue_max_jpy = Column(Float)            # 매출 구간 상한
    min_gp_jpy = Column(Float)                # 최소 GP 금액 (엔)
    min_gp_rate = Column(Float)               # 최소 GP율 (%)
    effective_from = Column(DateTime(timezone=True))
    effective_to = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExchangeRate(Base):
    __tablename__ = "exchange_rate"

    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String(10), nullable=False)  # USD, JPY, KRW 등
    to_currency = Column(String(10), nullable=False)    # KRW
    rate = Column(Float, nullable=False)
    effective_date = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
