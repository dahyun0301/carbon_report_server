# "/home" 경로 GET TemplateResponse API 정의하기

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/")
def home(request: Request):
    user_id = request.session.get("user_id")
    user_email = request.session.get("user_email")
    
    
    return templates.TemplateResponse("home.html", {"request": request, "user_id": user_id,"user_email": user_email})
