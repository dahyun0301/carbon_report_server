from fastapi import APIRouter, UploadFile, File, Form, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord
import pandas as pd
from io import BytesIO
import json

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/input", response_class=HTMLResponse)
def upload_page(request: Request):
    # 초기 페이지 로드 시 빈 데이터와 기본 폼 값 전달
    return templates.TemplateResponse("input.html", {
        "request": request,
        "results": "[]",
        "scopes": "[]",
        "company_name": "",
        "industry": "",
        "start": "",
        "end": "",
        "quota": ""
    })

@router.post("/upload-excel", response_class=HTMLResponse)
async def upload_excel(
    request: Request,
    file: UploadFile = File(...),
    company_name: str = Form(...),
    industry: str = Form(...),
    start: str = Form(...),  # YYYY-MM
    end: str = Form(...),    # YYYY-MM
    quota: float = Form(...),
    db: Session = Depends(get_db)
):
    # 엑셀 읽기
    contents = await file.read()
    df = pd.read_excel(BytesIO(contents))

    # 컬럼명 통일: 소문자, 공백->언더스코어, 특수문자 제거
    df.columns = (
        df.columns.str.strip()
                  .str.lower()
                  .str.replace(" ", "_")
                  .str.replace(r"[^0-9a-z_]", "", regex=True)
    )

    # 필수 컬럼 확인
    if "month" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"'month' 컬럼이 없습니다. 현재 컬럼: {df.columns.tolist()}"
        )

    # 컬럼명 매핑
    df.rename(columns={
        "electricity_(kwh)": "electricity",
        "gasoline_(l)": "gasoline",
        "natural_gas_(m3)": "natural_gas",
        "district_heating_(gj)": "district_heating"
    }, inplace=True)

    # 기존 기록 삭제
    db.query(EmissionRecord).delete()

    # DB 저장
    for _, row in df.iterrows():
        month = str(row["month"])
        electricity = row.get("electricity", 0)
        gasoline = row.get("gasoline", 0)
        natural_gas = row.get("natural_gas", 0)
        district_heating = row.get("district_heating", 0)
        total_emission = round(
            electricity * 0.417 +
            gasoline * 2.31 +
            natural_gas * 0.203 +
            district_heating * 110,
            2
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

    # 쿼리 후 JSON 직렬화
    records = db.query(EmissionRecord).all()
    results = [
        {"month": r.month,
         "electricity": r.electricity,
         "gasoline": r.gasoline,
         "natural_gas": r.natural_gas,
         "district_heating": r.district_heating,
         "total_emission": r.total_emission}
        for r in records
    ]
    scopes = [
        {"month": r.month,
         "scope1": round(r.gasoline * 2.31 + r.natural_gas * 0.203, 2),
         "scope2": round(r.electricity * 0.417 + r.district_heating * 110, 2)}
        for r in records
    ]

    # 템플릿 렌더링
    return templates.TemplateResponse("input.html", {
        "request": request,
        "results": json.dumps(results),
        "scopes": json.dumps(scopes),
        "company_name": company_name,
        "industry": industry,
        "start": start,
        "end": end,
        "quota": quota
    })
