from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.db import engine, Base
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# 앱 시작 시 한 번만 테이블 생성
@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


# 정적 파일 및 템플릿 디렉터리 연결
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


app.add_middleware(SessionMiddleware, secret_key="super-secret-key")


# 라우터 등록
from .routers import auth, home, report
app.include_router(auth.router)
app.include_router(home.router)
# app.include_router(report.router)
