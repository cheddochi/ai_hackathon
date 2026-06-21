from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.result import Todo
from app.models.transaction import ProfitSheetHeader
from app.schemas.approval import TodoOut, TodoUpdate

router = APIRouter(prefix="/todos", tags=["todo"])


@router.get("", response_model=List[TodoOut])
def list_todos(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Todo)
    if status:
        q = q.filter(Todo.status == status)
    if priority:
        q = q.filter(Todo.priority == priority)
    todos = q.order_by(Todo.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for todo in todos:
        header = db.query(ProfitSheetHeader).filter(ProfitSheetHeader.id == todo.header_id).first()
        out = TodoOut.model_validate(todo)
        if header:
            out.case_no = header.case_no
            out.customer_name = header.customer_name
        result.append(out)
    return result


@router.patch("/{todo_id}", response_model=TodoOut)
def update_todo(
    todo_id: int,
    update: TodoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if update.status is not None:
        todo.status = update.status
        if update.status == "DONE":
            from datetime import datetime
            todo.resolved_at = datetime.utcnow()
    if update.assignee_id is not None:
        todo.assignee_id = update.assignee_id
    if update.due_date is not None:
        todo.due_date = update.due_date
    if update.description is not None:
        todo.description = update.description

    db.commit()
    db.refresh(todo)
    return todo
