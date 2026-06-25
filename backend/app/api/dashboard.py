from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date
from typing import List

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.transaction import ProfitSheetHeader, ApprovalStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()

    # ── 집계 헬퍼 (total_revenue_jpy / gp_jpy 가 NULL인 행은 0으로 처리) ──
    # 상태 필터 없음 — 등록된 모든 건을 집계
    def _sum(q):
        row = q.first()
        return {
            "revenue": float(row.revenue or 0) if row else 0.0,
            "gp":      float(row.gp      or 0) if row else 0.0,
            "count":   int(row.count     or 0) if row else 0,
        }

    base_q = db.query(
        func.coalesce(func.sum(ProfitSheetHeader.total_revenue_jpy), 0).label("revenue"),
        func.coalesce(func.sum(ProfitSheetHeader.gp_jpy), 0).label("gp"),
        func.count(ProfitSheetHeader.id).label("count"),
    )

    # 오늘 (등록일 기준 — timezone 무시하고 DATE 비교)
    today_data = _sum(
        base_q.filter(func.date(ProfitSheetHeader.created_at) == today)
    )

    # 월간
    monthly_data = _sum(
        base_q.filter(
            extract("year",  ProfitSheetHeader.created_at) == today.year,
            extract("month", ProfitSheetHeader.created_at) == today.month,
        )
    )

    # 연간
    yearly_data = _sum(
        base_q.filter(
            extract("year", ProfitSheetHeader.created_at) == today.year,
        )
    )

    # 상태별 건수 (모든 상태)
    status_rows = (
        db.query(ProfitSheetHeader.status, func.count().label("cnt"))
        .group_by(ProfitSheetHeader.status)
        .all()
    )
    status_counts = {s.value: c for s, c in status_rows}

    # 인간 결재 현황
    human_approved = (
        db.query(func.count())
        .filter(ProfitSheetHeader.human_decision == "APPROVED")
        .scalar() or 0
    )
    human_rejected = (
        db.query(func.count())
        .filter(ProfitSheetHeader.human_decision == "REJECTED")
        .scalar() or 0
    )

    monthly_rev = monthly_data["revenue"]
    monthly_gp  = monthly_data["gp"]

    return {
        "today": {
            "revenue_jpy": today_data["revenue"],
            "gp_jpy":      today_data["gp"],
            "count":       today_data["count"],
        },
        "monthly": {
            "revenue_jpy": monthly_rev,
            "gp_jpy":      monthly_gp,
            "count":       monthly_data["count"],
            "gp_rate":     monthly_gp / monthly_rev * 100 if monthly_rev else 0.0,
        },
        "yearly": {
            "revenue_jpy": yearly_data["revenue"],
            "gp_jpy":      yearly_data["gp"],
            "count":       yearly_data["count"],
        },
        "status_counts": status_counts,
        "human_decision": {
            "approved": int(human_approved),
            "rejected": int(human_rejected),
        },
    }


@router.get("/top-customers")
def get_top_customers(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """거래처별 GP 합계 TOP N — 상태 무관, total_revenue_jpy/gp_jpy가 있는 건만"""
    rows = (
        db.query(
            ProfitSheetHeader.customer_name,
            ProfitSheetHeader.customer_type,
            func.coalesce(func.sum(ProfitSheetHeader.total_revenue_jpy), 0).label("revenue"),
            func.coalesce(func.sum(ProfitSheetHeader.gp_jpy), 0).label("gp"),
            func.count(ProfitSheetHeader.id).label("case_count"),
        )
        .filter(ProfitSheetHeader.customer_name.isnot(None))
        .group_by(ProfitSheetHeader.customer_name, ProfitSheetHeader.customer_type)
        .order_by(func.coalesce(func.sum(ProfitSheetHeader.gp_jpy), 0).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "customer_name": r.customer_name,
            "customer_type": r.customer_type,
            "revenue_jpy":   float(r.revenue),
            "gp_jpy":        float(r.gp),
            "gp_rate":       float(r.gp) / float(r.revenue) * 100 if r.revenue else 0.0,
            "case_count":    int(r.case_count),
        }
        for r in rows
    ]


@router.get("/productivity")
def get_productivity(
    year_month: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    직원별 생산성 — ProductivityHistory 대신 ProfitSheetHeader에서 직접 집계.
    (point 컬럼이 None이면 건수 × 1.0으로 대체)
    """
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")

    year, month = map(int, year_month.split("-"))

    rows = (
        db.query(
            ProfitSheetHeader.assignee_id,
            ProfitSheetHeader.assignee_name,
            func.coalesce(func.sum(ProfitSheetHeader.point), func.count(ProfitSheetHeader.id)).label("total_point"),
            func.coalesce(func.sum(ProfitSheetHeader.gp_jpy), 0).label("total_gp"),
            func.count(ProfitSheetHeader.id).label("case_count"),
        )
        .filter(
            extract("year",  ProfitSheetHeader.created_at) == year,
            extract("month", ProfitSheetHeader.created_at) == month,
            ProfitSheetHeader.assignee_name.isnot(None),
        )
        .group_by(ProfitSheetHeader.assignee_id, ProfitSheetHeader.assignee_name)
        .all()
    )

    result = []
    for r in rows:
        total_point = float(r.total_point or 0)
        grade = (
            "우수" if total_point >= 120
            else "정상" if total_point >= 80
            else "관리" if total_point >= 60
            else "개선"
        )
        # 부서 정보 조회
        user = db.query(User).filter(User.id == r.assignee_id).first()
        result.append({
            "user_id":    r.assignee_id,
            "user_name":  r.assignee_name or "Unknown",
            "department": user.department if user else "",
            "total_point": total_point,
            "total_gp":   float(r.total_gp),
            "case_count": int(r.case_count),
            "grade":      grade,
            "year_month": year_month,
        })

    return sorted(result, key=lambda x: x["total_point"], reverse=True)


@router.get("/gp-by-job-code")
def get_gp_by_job_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """업무코드별 GP — 상태 무관 전체 집계"""
    rows = (
        db.query(
            ProfitSheetHeader.job_code,
            func.coalesce(func.sum(ProfitSheetHeader.total_revenue_jpy), 0).label("revenue"),
            func.coalesce(func.sum(ProfitSheetHeader.gp_jpy), 0).label("gp"),
            func.count(ProfitSheetHeader.id).label("count"),
        )
        .group_by(ProfitSheetHeader.job_code)
        .order_by(func.coalesce(func.sum(ProfitSheetHeader.gp_jpy), 0).desc())
        .all()
    )
    return [
        {
            "job_code":    r.job_code,
            "revenue_jpy": float(r.revenue),
            "gp_jpy":      float(r.gp),
            "gp_rate":     float(r.gp) / float(r.revenue) * 100 if r.revenue else 0.0,
            "count":       int(r.count),
        }
        for r in rows
    ]
