from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User, EmissionRecord, ReportInfo

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/matching")
def match_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:

        return RedirectResponse(url="/auth/login", status_code=303)

    user = db.query(User).filter(User.id == user_id).first()
    report = db.query(ReportInfo).filter(ReportInfo.user_id == user_id).order_by(ReportInfo.id.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="보고서 정보가 없습니다.")


    # 회사명이 비어 있을 경우 EmissionRecord에서 유추
    company_name = report.company
    if not company_name:
        first_record = db.query(EmissionRecord).filter(EmissionRecord.user_id == user_id).first()
        if first_record:
            company_name = first_record.company
        else:
            company_name = "(미입력)"#

    records = db.query(EmissionRecord).filter(
        EmissionRecord.user_id == user_id,
        EmissionRecord.month >= report.start_month,
        EmissionRecord.month <= report.end_month
    ).all()

    total_emission = sum([r.total_emission for r in records])
    remaining = round(report.allowance - total_emission, 2)
    status = "남은 배출권" if remaining > 0 else "초과 배출량"
    status_value = abs(remaining)

    all_reports = db.query(ReportInfo).all()
    company_emissions = []
    for rep in all_reports:
        rep_user = db.query(User).filter(User.id == rep.user_id).first()

        rep_records = db.query(EmissionRecord).filter(
            EmissionRecord.user_id == rep.user_id,
            EmissionRecord.month >= rep.start_month,
            EmissionRecord.month <= rep.end_month
        ).all()
        emission_sum = sum([r.total_emission for r in rep_records])
        difference = round(rep.allowance - emission_sum, 2)


        rep_company_name = rep.company
        if not rep_company_name:
            first_rec = db.query(EmissionRecord).filter(EmissionRecord.user_id == rep.user_id).first()
            rep_company_name = first_rec.company if first_rec else "(미입력)"

        company_emissions.append({
            "id": rep.user_id,
            "email": rep_user.email,
            "company": rep_company_name,
            "industry": rep_user.industry,
            "difference": difference
        })

    # 본인 제외
    excess_companies = [c for c in company_emissions if c["difference"] < 0 and c["id"] != user_id]
    remaining_companies = [c for c in company_emissions if c["difference"] > 0 and c["id"] != user_id]

    return templates.TemplateResponse("match.html", {
        "request": request,
        "user_company": company_name,
        "user_industry": user.industry,
        "status": status,
        "status_value": status_value,
        "excess_companies": excess_companies,
        "remaining_companies": remaining_companies
    })
