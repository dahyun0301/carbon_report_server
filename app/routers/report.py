from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord, ReportInfo

import matplotlib.pyplot as plt
import matplotlib
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")

FONT_PATH = "app/static/fonts/NanumHumanBold.ttf"
FONT_NAME = "NanumHumanBold"
GRAPH_PATH = "app/static/img/graph.png"
PDF_PATH = "app/static/report.pdf"

pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_graph(months, emissions):
    plt.figure(figsize=(6, 3))
    plt.bar(months, emissions, color='skyblue')
    plt.xlabel('Month')
    plt.ylabel('Emissions (kgCO₂)')
    plt.title('Monthly Emissions')
    plt.tight_layout()
    plt.savefig(GRAPH_PATH)
    plt.close()

@router.get("/report", response_class=HTMLResponse)
def report_page(request: Request):
    return templates.TemplateResponse("report.html", {"request": request})

@router.get("/report-preview", response_class=HTMLResponse)
def report_preview(db: Session = Depends(get_db)):
    return FileResponse(PDF_PATH, media_type="application/pdf")

@router.get("/report-download")
def report_download(db: Session = Depends(get_db)):
    return FileResponse(PDF_PATH, media_type="application/pdf", filename="carbon_report.pdf")

@router.get("/generate-report")
def generate_pdf_report(db: Session = Depends(get_db)):
    info = db.query(ReportInfo).first()
    records = db.query(EmissionRecord).filter(
        EmissionRecord.month >= info.start_month,
        EmissionRecord.month <= info.end_month
    ).order_by(EmissionRecord.month).all()

    total_emission = sum([r.total_emission for r in records])
    scope1 = sum([r.gasoline * 2.31 + r.natural_gas * 0.203 for r in records])
    scope2 = sum([r.electricity * 0.417 + r.district_heating * 110 for r in records])
    remaining = round(info.allowance - total_emission, 2)

    # 그래프 이미지 생성
    months = [r.month for r in records]
    emissions = [r.total_emission for r in records]
    generate_graph(months, emissions)

    # PDF 생성
    c = canvas.Canvas(PDF_PATH, pagesize=A4)
    c.setFont(FONT_NAME, 14)
    c.drawCentredString(300, 800, "탄소 배출 보고서")

    c.setFont(FONT_NAME, 10)
    c.drawString(50, 770, f"기업명: {info.company}")
    c.drawString(300, 770, f"분석 기간: {info.start_month} ~ {info.end_month}")

    c.drawString(50, 740, "[Scope 배출량 요약]")
    c.drawString(70, 725, f"Scope 1: {round(scope1, 2)} kgCO₂")
    c.drawString(70, 710, f"Scope 2: {round(scope2, 2)} kgCO₂")
    c.drawString(70, 695, f"총 배출량: {round(total_emission, 2)} kgCO₂")

    c.drawString(50, 670, "[규제 기준 초과 여부]")
    if remaining < 0:
        c.drawString(70, 655, f"기준 초과: 초과 배출량: {abs(remaining)} kgCO₂")
    else:
        c.drawString(70, 655, f"기준 미만: 남은 배출권: {remaining} kgCO₂")

    c.drawString(50, 620, "[탄소 배출량 시각화]")
    c.drawImage(ImageReader(GRAPH_PATH), 50, 400, width=500, height=200)

    c.save()
    return {"message": "PDF generated successfully"}
