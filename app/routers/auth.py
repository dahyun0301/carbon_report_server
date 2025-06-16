# app/routers/auth.py

from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..db import SessionLocal
from .. import crud
from .. import schemas



router = APIRouter(prefix="/auth", tags=["auth"])


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
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email

    # POST 이후 확실히 GET으로 전환하기 위해 303 사용
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/register")
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    industry: str = Form(None),
    db: Session = Depends(get_db)
):
    existing_user = crud.get_user_by_email(db, email=email)
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "이미 존재하는 이메일입니다."}
        )

    user_create = schemas.UserCreate(email=email, password=password,industry=industry)
    crud.create_user(db, user_create)
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
