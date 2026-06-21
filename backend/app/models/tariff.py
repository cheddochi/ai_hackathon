from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class TariffTransport(Base):
    __tablename__ = "tariff_transport"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("profit_sheet_header.id"))
    origin_port = Column(String(100))
    dest_port = Column(String(100))
    partner_name = Column(String(200))
    charge_code = Column(String(50))   # OF, AF 등
    currency = Column(String(10))
    amount = Column(Float)
    amount_jpy = Column(Float)
    container_type = Column(String(50))
    transport_mode = Column(String(10))  # SEA, AIR
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class TariffCustoms(Base):
    __tablename__ = "tariff_customs"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("profit_sheet_header.id"))
    port = Column(String(100))
    direction = Column(String(10))     # EXPORT, IMPORT
    partner_name = Column(String(200))
    charge_code = Column(String(50))
    currency = Column(String(10))
    amount = Column(Float)
    amount_jpy = Column(Float)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class TariffWarehouse(Base):
    __tablename__ = "tariff_warehouse"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("profit_sheet_header.id"))
    port = Column(String(100))
    partner_name = Column(String(200))
    charge_code = Column(String(50))   # STORAGE, DEVAN, VANNING 등
    service_type = Column(String(100))
    currency = Column(String(10))
    amount = Column(Float)
    amount_jpy = Column(Float)
    unit = Column(String(50))          # per RT, per CBM 등
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
