from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date
from typing import List

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.transaction import ProfitSheetHeader, ApprovalStatus
from app.models.result import ProductivityHistory

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    year_month = today.strftime("%Y-%m")

    approved_statuses = [ApprovalStatus.APPROVED, ApprovalStatus.CONDITIONAL]

    # 오늘 매출/GP
    today_data = (
        db.query(
            func.sum(ProfitSheetHeader.total_revenue_jpy).label("revenue"),
            func.sum(ProfitSheetHeader.gp_jpy).label("gp"),
            func.count().label("count"),
        )
        .filter(
            func.date(ProfitSheetHeader.created_at) == today,
            ProfitSheetHeader.status.in_(approved_statuses),
        )
        .first()
    )

    # 월간 매출/GP
    monthly_data = (
        db.query(
            func.sum(ProfitSheetHeader.total_revenue_jpy).label("revenue"),
            func.sum(ProfitSheetHeader.gp_jpy).label("gp"),
            func.count().label("count"),
        )
        .filter(
            extract("year", ProfitSheetHeader.created_at) == today.year,
            extract("month", ProfitSheetHeader.created_at) == today.month,
            ProfitSheetHeader.status.in_(approved_statuses),
        )
        .first()
    )

    # 연간 매출/GP
    yearly_data = (
        db.query(
            func.sum(ProfitSheetHeader.total_revenue_jpy).label("revenue"),
            func.sum(ProfitSheetHeader.gp_jpy).label("gp"),
            func.count().label("count"),
        )
        .filter(
            extract("year", ProfitSheetHeader.created_at) == today.year,
            ProfitSheetHeader.status.in_(approved_statuses),
        )
        .first()
    )

    # 상태별 건수
    status_counts = (
        db.query(ProfitSheetHeader.status, func.count().label("count"))
        .group_by(ProfitSheetHeader.status)
        .all()
    )

    return {
        "today": {
            "revenue_jpy": float(today_data.revenue or 0),
            "gp_jpy": float(today_data.gp or 0),
            "count": int(today_data.count or 0),
        },
        "monthly": {
            "revenue_jpy": float(monthly_data.revenue or 0),
            "gp_jpy": float(monthly_data.gp or 0),
            "count": int(monthly_data.count or 0),
            "gp_rate": (
                float(monthly_data.gp or 0) / float(monthly_data.revenue or 1) * 100
                if monthly_data.revenue
                else 0
            ),
        },
        "yearly": {
            "revenue_jpy": float(yearly_data.revenue or 0),
            "gp_jpy": float(yearly_data.gp or 0),
            "count": int(yearly_data.count or 0),
        },
        "status_counts": {s.value: c for s, c in status_counts},
    }


@router.get("/top-customers")
def get_top_customers(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approved_statuses = [ApprovalStatus.APPROVED, ApprovalStatus.CONDITIONAL]
    rows = (
        db.query(
            ProfitSheetHeader.customer_name,
            ProfitSheetHeader.customer_type,
            func.sum(ProfitSheetHeader.total_revenue_jpy).label("revenue"),
            func.sum(ProfitSheetHeader.gp_jpy).label("gp"),
            func.count().label("case_count"),
        )
        .filter(ProfitSheetHeader.status.in_(approved_statuses))
        .group_by(ProfitSheetHeader.customer_name, ProfitSheetHeader.customer_type)
        .order_by(func.sum(ProfitSheetHeader.gp_jpy).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "customer_name": r.customer_name,
            "customer_type": r.customer_type,
            "revenue_jpy": float(r.revenue or 0),
            "gp_jpy": float(r.gp or 0),
            "gp_rate": float(r.gp or 0) / float(r.revenue or 1) * 100 if r.revenue else 0,
            "case_count": int(r.case_count or 0),
        }
        for r in rows
    ]


@router.get("/productivity")
def get_productivity(
    year_month: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")

    rows = (
        db.query(
            ProductivityHistory.user_id,
            func.sum(ProductivityHistory.point).label("total_point"),
            func.count().label("case_count"),
        )
        .filter(ProductivityHistory.year_month == year_month)
        .group_by(ProductivityHistory.user_id)
        .all()
    )

    result = []
    for r in rows:
        user = db.query(User).filter(User.id == r.user_id).first()
        total_point = float(r.total_point or 0)
        grade = (
            "우수" if total_point >= 120
            else "정상" if total_point >= 80
            else "관리" if total_point >= 60
            else "개선"
        )
        result.append({
            "user_id": r.user_id,
            "user_name": user.name if user else "Unknown",
            "department": user.department if user else "",
            "total_point": total_point,
            "case_count": int(r.case_count or 0),
            "grade": grade,
            "year_month": year_month,
        })

    return sorted(result, key=lambda x: x["total_point"], reverse=True)


@router.get("/gp-by-job-code")
def get_gp_by_job_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approved_statuses = [ApprovalStatus.APPROVED, ApprovalStatus.CONDITIONAL]
    rows = (
        db.query(
            ProfitSheetHeader.job_code,
            func.sum(ProfitSheetHeader.total_revenue_jpy).label("revenue"),
            func.sum(ProfitSheetHeader.gp_jpy).label("gp"),
            func.count().label("count"),
        )
        .filter(ProfitSheetHeader.status.in_(approved_statuses))
        .group_by(ProfitSheetHeader.job_code)
        .all()
    )
    return [
        {
            "job_code": r.job_code,
            "revenue_jpy": float(r.revenue or 0),
            "gp_jpy": float(r.gp or 0),
            "gp_rate": float(r.gp or 0) / float(r.revenue or 1) * 100 if r.revenue else 0,
            "count": int(r.count or 0),
        }
        for r in rows
    ]
