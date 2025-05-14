from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/input")
def input_page(request: Request):
    return templates.TemplateResponse("input.html", {"request": request})