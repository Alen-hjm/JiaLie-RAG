from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import current_user
from ..models import AdminUser
from ..schemas import LoginIn, UserOut
from ..security import create_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "用户名或密码不正确"})
    response.set_cookie("session", create_token(user.username), httponly=True, samesite="lax", secure=False, max_age=43200)
    return UserOut(username=user.username)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("session")


@router.get("/me", response_model=UserOut)
def me(user: AdminUser = Depends(current_user)):
    return UserOut(username=user.username)

