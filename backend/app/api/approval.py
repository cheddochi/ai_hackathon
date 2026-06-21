from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.transaction import ProfitSheetHeader, ProfitSheetDetail, ApprovalStatus
from app.models.result import ApprovalHistory, RuleEvaluationLog, Todo, ProductivityHistory
from app.schemas.approval import ApprovalOut, TodoOut, TodoUpdate
from app.services.approval_engine import run_approval

router = APIRouter(prefix="/approvals", tags=["approval"])


@router.post("/{sheet_id}/run", response_model=ApprovalOut)
def run_approval_engine(
    sheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    header = db.query(ProfitSheetHeader).filter(ProfitSheetHeader.id == sheet_id).first()
    if not header:
        raise HTTPException(status_code=404, detail="Profit Sheet not found")

    details = db.query(ProfitSheetDetail).filter(ProfitSheetDetail.header_id == sheet_id).all()

    result = run_approval(header, details, db)

    # ApprovalHistory 저장
    history = ApprovalHistory(
        header_id=sheet_id,
        judgment=result.judgment,
        gp_rule_passed=all(r.passed for r in result.rule_results if r.rule_code == "GP_CHECK"),
        partner_fee_passed=all(r.passed for r in result.rule_results if r.rule_code == "PARTNER_FEE"),
        internal_resource_passed=all(r.passed for r in result.rule_results if r.rule_code == "INTERNAL_RESOURCE"),
        cost_omission_passed=all(r.passed for r in result.rule_results if r.rule_code == "COST_OMISSION"),
        gp_jpy_snapshot=header.gp_jpy,
        gp_rate_snapshot=header.gp_rate,
        revenue_snapshot=header.total_revenue_jpy,
        rule_version="v1.0.0",
        approved_by=current_user.id,
    )
    db.add(history)
    db.flush()

    # RuleEvaluationLog 저장
    for r in result.rule_results:
        log = RuleEvaluationLog(
            approval_history_id=history.id,
            rule_code=r.rule_code,
            rule_name=r.rule_name,
            passed=r.passed,
            input_value=r.input_value,
            threshold_value=r.threshold_value,
            message=r.message,
        )
        db.add(log)

    # Todo 생성
    for todo_data in result.todos:
        todo = Todo(
            header_id=sheet_id,
            title=todo_data["title"],
            rule_code=todo_data["rule_code"],
            priority=todo_data["priority"],
            assignee_id=header.assignee_id,
        )
        db.add(todo)

    # 헤더 상태 업데이트
    status_map = {
        "APPROVED": ApprovalStatus.APPROVED,
        "CONDITIONAL": ApprovalStatus.CONDITIONAL,
        "REVIEW": ApprovalStatus.REVIEW,
        "REJECTED": ApprovalStatus.REJECTED,
    }
    header.status = status_map.get(result.judgment, ApprovalStatus.PENDING)

    # 생산성 포인트 귀속 (APPROVED, CONDITIONAL 시)
    if result.judgment in ("APPROVED", "CONDITIONAL") and header.assignee_id:
        from datetime import datetime
        year_month = datetime.now().strftime("%Y-%m")
        productivity = ProductivityHistory(
            user_id=header.assignee_id,
            header_id=sheet_id,
            job_code=header.job_code,
            point=header.point or 1.0,
            year_month=year_month,
        )
        db.add(productivity)

    db.commit()
    db.refresh(history)

    # 응답에 룰 로그 포함
    from app.schemas.approval import RuleResultOut
    history_out = ApprovalOut.model_validate(history)
    history_out.rule_logs = [
        RuleResultOut(
            rule_code=r.rule_code,
            rule_name=r.rule_name,
            passed=r.passed,
            input_value=r.input_value,
            threshold_value=r.threshold_value,
            message=r.message,
        )
        for r in result.rule_results
    ]
    return history_out


@router.get("/{sheet_id}/history", response_model=List[ApprovalOut])
def get_approval_history(
    sheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    histories = (
        db.query(ApprovalHistory)
        .filter(ApprovalHistory.header_id == sheet_id)
        .order_by(ApprovalHistory.created_at.desc())
        .all()
    )
    return histories
