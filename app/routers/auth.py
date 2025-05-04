# app/routers/auth.py

from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..db import SessionLocal
from .. import crud

# 1) auth 관련 엔드포인트를 /auth 아래로 묶고, Swagger 문서 정리용 태그 추가
router = APIRouter(prefix="/auth", tags=["auth"])

# 2) uvicorn을 프로젝트 루트(myapp/)에서 실행할 때에도 안정적으로 찾히도록 경로 수정
templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/login")
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = crud.authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "잘못된 이메일 또는 비밀번호입니다."
            }
        )
    # TODO: 세션 생성 또는 JWT 발급 로직 추가
    # POST 이후 확실히 GET으로 전환하기 위해 303 사용
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
