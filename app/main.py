from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.db import engine, Base
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)



app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


app.add_middleware(SessionMiddleware, secret_key="super-secret-key")



from .routers import auth, home, report, input, match, previous
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(report.router)
app.include_router(input.router)
app.include_router(match.router)
app.include_router(previous.router)

