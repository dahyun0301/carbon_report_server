from fastapi import APIRouter, Form, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord, ReportInfo
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/previous", response_class=HTMLResponse)
def previous_page(request: Request):
    user_email = request.session.get("user_email")
    return templates.TemplateResponse("previous.html", {
        "request": request,
        "user_email": user_email
    })

@router.post("/previous", response_class=HTMLResponse)
def run_previous_analysis(
    request: Request,
    start_month: str = Form(...),
    end_month: str = Form(...),
    allowance: float = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    user_email = request.session.get("user_email")
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    # 최신 보고서에 빈 company 저장
    db.add(ReportInfo(
        user_id=user_id,
        company="",  # 기업명 생략
        start_month=start_month,
        end_month=end_month,
        allowance=allowance
    ))
    db.commit()

    records = db.query(EmissionRecord).filter(
        EmissionRecord.user_id == user_id,
        EmissionRecord.month >= start_month,
        EmissionRecord.month <= end_month
    ).order_by(EmissionRecord.month).all()

    if not records:
        return templates.TemplateResponse("previous.html", {
            "request": request,
            "user_email": user_email,
            "error": "해당 기간에 대한 데이터가 없습니다."
        })

    results, scopes = [], []
    for r in records:
        results.append({
            "month": r.month,
            "electricity": r.electricity,
            "gasoline": r.gasoline,
            "natural_gas": r.natural_gas,
            "district_heating": r.district_heating,
            "total_emission": r.total_emission
        })
        scopes.append({
            "month": r.month,
            "scope1": round(r.gasoline * 2.31 + r.natural_gas * 0.203, 2),
            "scope2": round(r.electricity * 0.417 + r.district_heating * 110, 2)
        })

    return templates.TemplateResponse("previous.html", {
        "request": request,
        "user_email": user_email,
        "results": json.dumps(results, default=str),
        "scopes": json.dumps(scopes, default=str),
        "allowance": allowance
    })
