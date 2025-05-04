from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .db import engine, Base

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI()

# 정적 파일 및 템플릿 디렉터리 연결
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
from .routers import auth, home, report
app.include_router(auth.router)
# app.include_router(home.router)
# app.include_router(report.router)
