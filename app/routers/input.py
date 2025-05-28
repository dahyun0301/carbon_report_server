from fastapi import APIRouter, UploadFile, File, Form, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
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
    return templates.TemplateResponse("input.html", {"request": request})

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
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    df.rename(columns={
        "electricity (kWh)": "electricity",
        "gasoline (L)": "gasoline",
        "natural_gas (m³)": "natural_gas",
        "district_heating (GJ)": "district_heating"
    }, inplace=True)

    # db.query(EmissionRecord).filter(EmissionRecord.user_id == user_id).delete()
    # db.query(ReportInfo).filter(ReportInfo.user_id == user_id).delete()
    # db.commit()

    for _, row in df.iterrows():
        month = str(row["month"])[:7]
        total_emission = round(
            row["electricity"] * 0.417 +
            row["gasoline"] * 2.31 +
            row["natural_gas"] * 0.203 +
            row["district_heating"] * 110, 2
        )

        record = EmissionRecord(
            user_id=user_id,
            company=company,
            month=month,
            electricity=row["electricity"],
            gasoline=row["gasoline"],
            natural_gas=row["natural_gas"],
            district_heating=row["district_heating"],
            total_emission=total_emission
        )
        db.add(record)
    
    db.add(ReportInfo(
        user_id=user_id,
        company=company,
        start_month=start_month,
        end_month=end_month,
        allowance=allowance
    ))
    
    db.commit()

    # 필터링 및 결과 전송
    filtered = db.query(EmissionRecord).filter(
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

    return templates.TemplateResponse("input.html", {
        "request": request,
        "results": json.dumps(results, default=str),
        "scopes": json.dumps(scopes, default=str),
        "company": company,
        "allowance": allowance
    })


    
    
