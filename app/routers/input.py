from fastapi import APIRouter, UploadFile, File, Form, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord, ReportInfo
import pandas as pd
from io import BytesIO
import json
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/input", response_class=HTMLResponse)
def input_page(request: Request):
    user_email = request.session.get("user_email")
    return templates.TemplateResponse("input.html", {
        "request": request,
        "user_email": user_email
    })

@router.post("/input-excel", response_class=HTMLResponse)
async def input_excel(
    request: Request,
    file: UploadFile = File(...),
    company: str = Form(...),
    start_month: str = Form(...),
    end_month: str = Form(...),
    allowance: float = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    df.rename(columns={
        "electricity (kWh)": "electricity",
        "gasoline (L)": "gasoline",
        "natural_gas (m³)": "natural_gas",
        "district_heating (GJ)": "district_heating"
    }, inplace=True)

    existing_records = db.query(EmissionRecord).filter(EmissionRecord.user_id == user_id).all()
    existing_map = {(r.month, r.company): r for r in existing_records}

    for _, row in df.iterrows():
        month = str(row["month"])[:7]
        total_emission = round(
            row["electricity"] * 0.417 +
            row["gasoline"] * 2.31 +
            row["natural_gas"] * 0.203 +
            row["district_heating"] * 110, 2
        )

        key = (month, company)
        should_save = True

        if key in existing_map:
            record = existing_map[key]
            if (
                round(record.electricity, 2) == round(row["electricity"], 2) and
                round(record.gasoline, 2) == round(row["gasoline"], 2) and
                round(record.natural_gas, 2) == round(row["natural_gas"], 2) and
                round(record.district_heating, 2) == round(row["district_heating"], 2)
            ):
                should_save = False
            else:
                db.delete(record)

        if should_save:
            db.add(EmissionRecord(
                user_id=user_id,
                company=company,
                month=month,
                electricity=row["electricity"],
                gasoline=row["gasoline"],
                natural_gas=row["natural_gas"],
                district_heating=row["district_heating"],
                total_emission=total_emission
            ))

    db.add(ReportInfo(
        user_id=user_id,
        company=company,
        start_month=start_month,
        end_month=end_month,
        allowance=allowance
    ))
    
    db.commit()

    filtered = db.query(EmissionRecord).filter(
        EmissionRecord.user_id == user_id,
        EmissionRecord.month >= start_month,
        EmissionRecord.month <= end_month
    ).order_by(EmissionRecord.month).all()

    results, scopes, seen = [], [], set()
    for r in filtered:
        if r.month not in seen:
            seen.add(r.month)
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

    user_email = request.session.get("user_email")
    return templates.TemplateResponse("input.html", {
        "request": request,
        "user_email": user_email,
        "results": json.dumps(results, default=str),
        "scopes": json.dumps(scopes, default=str),
        "company": company,
        "allowance": allowance
    })
