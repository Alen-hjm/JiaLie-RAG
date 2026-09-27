from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import AdminUser
from .security import read_token


def current_user(session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> AdminUser:
    username = read_token(session) if session else None
    user = db.scalar(select(AdminUser).where(AdminUser.username == username)) if username else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "AUTH_REQUIRED", "message": "请先登录"})
    return user

