from fastapi import APIRouter, UploadFile, File, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord
import pandas as pd
from io import BytesIO
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    # 새로고침 시 그래프 숨기기 위해 빈 데이터 전달
    return templates.TemplateResponse("upload.html", {"request": request, "results": "[]", "scopes": "[]"})

@router.post("/upload-excel", response_class=HTMLResponse)
async def upload_excel(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    df.rename(columns={
        "electricity (kWh)": "electricity",
        "gasoline (L)": "gasoline",
        "natural_gas (m³)": "natural_gas",
        "district_heating (GJ)": "district_heating"
    }, inplace=True)

    db.query(EmissionRecord).delete()

    for _, row in df.iterrows():
        month = str(row["month"])
        electricity = row["electricity"]
        gasoline = row["gasoline"]
        natural_gas = row["natural_gas"]
        district_heating = row["district_heating"]

        total_emission = round(
            electricity * 0.417 +
            gasoline * 2.31 +
            natural_gas * 0.203 +
            district_heating * 110, 2
        )

        record = EmissionRecord(
            month=month,
            electricity=electricity,
            gasoline=gasoline,
            natural_gas=natural_gas,
            district_heating=district_heating,
            total_emission=total_emission
        )
        db.add(record)
        db.commit()

    records = db.query(EmissionRecord).all()
    results = [
        {
            "month": r.month,
            "electricity": r.electricity,
            "gasoline": r.gasoline,
            "natural_gas": r.natural_gas,
            "district_heating": r.district_heating,
            "total_emission": r.total_emission,
        }
        for r in records
    ]

    scopes = [
        {
            "month": r.month,
            "scope1": round(r.gasoline * 2.31 + r.natural_gas * 0.203, 2),
            "scope2": round(r.electricity * 0.417 + r.district_heating * 110, 2)
        }
        for r in records
    ]

    return templates.TemplateResponse("upload.html", {
        "request": request,
        "results": json.dumps(results),
        "scopes": json.dumps(scopes)
    })
