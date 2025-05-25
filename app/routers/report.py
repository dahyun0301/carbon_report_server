from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord, ReportInfo

import matplotlib.pyplot as plt
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
GRAPH_PATH_TOTAL = "app/static/img/graph_total.png"
GRAPH_PATH_SCOPE = "app/static/img/graph_scope.png"
PDF_PATH = "app/static/report.pdf"

pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/report", response_class=HTMLResponse)
def report_page(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return templates.TemplateResponse("report.html", {"request": request})

@router.get("/report-preview", response_class=HTMLResponse)
def report_preview():
    return FileResponse(PDF_PATH, media_type="application/pdf")

@router.get("/report-download")
def report_download():
    return FileResponse(PDF_PATH, media_type="application/pdf", filename="carbon_report.pdf")

@router.get("/generate-report")
def generate_pdf_report(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    info = db.query(ReportInfo).filter(ReportInfo.user_id == user_id).first()
    if not info:
        raise HTTPException(status_code=404, detail="사용자의 보고서 정보가 없습니다.")

    records = db.query(EmissionRecord).filter(
        EmissionRecord.user_id == user_id,
        EmissionRecord.month >= info.start_month,
        EmissionRecord.month <= info.end_month
    ).order_by(EmissionRecord.month).all()

    if not records:
        raise HTTPException(status_code=404, detail="해당 기간에 대한 배출 데이터가 없습니다.")

    months = [r.month for r in records]
    total_emissions = [r.total_emission for r in records]
    scope1_list = [r.gasoline * 2.31 + r.natural_gas * 0.203 for r in records]
    scope2_list = [r.electricity * 0.417 + r.district_heating * 110 for r in records]

    total_emission_sum = sum(total_emissions)
    scope1_sum = sum(scope1_list)
    scope2_sum = sum(scope2_list)
    remaining = round(info.allowance - total_emission_sum, 2)

    # 그래프 생성
    generate_total_graph(months, total_emissions)
    generate_scope_graph(months, scope1_list, scope2_list)

    # PDF 생성
    c = canvas.Canvas(PDF_PATH, pagesize=A4)
    c.setFont(FONT_NAME, 14)
    c.drawCentredString(300, 800, "탄소 배출 보고서")

    c.setFont(FONT_NAME, 10)
    c.drawString(50, 770, f"기업명: {info.company}")
    c.drawString(300, 770, f"분석 기간: {info.start_month} ~ {info.end_month}")

    c.drawString(50, 740, "[Scope 배출량 요약]")
    c.drawString(70, 725, f"Scope 1: {round(scope1_sum, 2)} kgCO₂")
    c.drawString(70, 710, f"Scope 2: {round(scope2_sum, 2)} kgCO₂")
    c.drawString(70, 695, f"총 배출량: {round(total_emission_sum, 2)} kgCO₂")

    c.drawString(50, 670, "[규제 기준 초과 여부]")
    if remaining < 0:
        c.drawString(70, 655, f"기준 초과: 초과 배출량: {abs(remaining)} kgCO₂")
    else:
        c.drawString(70, 655, f"기준 미만: 남은 배출권: {remaining} kgCO₂")

    c.drawString(50, 620, "[총 배출량 그래프]")
    c.drawImage(ImageReader(GRAPH_PATH_TOTAL), 50, 410, width=500, height=160)

    c.drawString(50, 390, "[Scope 1 & 2 그래프]")
    c.drawImage(ImageReader(GRAPH_PATH_SCOPE), 50, 210, width=500, height=160)

    # 피드백
    c.drawString(50, 190, "[피드백]")
    c.drawString(70, 175, f"총 배출량: {round(total_emission_sum, 2)} kgCO₂")
    c.drawString(70, 160, f"Scope 1 비중: {round(scope1_sum / total_emission_sum * 100, 2)}%")
    c.drawString(70, 145, f"Scope 2 비중: {round(scope2_sum / total_emission_sum * 100, 2)}%")
    trend = "증가" if total_emissions[-1] > total_emissions[0] else "감소"
    c.drawString(70, 130, f"배출량 트렌드: 전반적으로 {trend} 추세")
    if remaining < 0:
        c.drawString(70, 115, "조언: 배출량 저감을 위한 에너지 효율 개선이 필요합니다.")
    else:
        c.drawString(70, 115, "조언: 좋은 경과입니다. 현재 수준을 유지하세요.")

    c.save()
    return {"message": "PDF generated successfully"}

def generate_total_graph(months, emissions):
    plt.figure(figsize=(6, 3))
    plt.bar(months, emissions, color='skyblue')
    plt.xlabel('Date')
    plt.ylabel('Emissions (kgCO₂)')
    plt.title('Total Emissions')
    plt.tight_layout()
    plt.savefig(GRAPH_PATH_TOTAL)
    plt.close()

def generate_scope_graph(months, scope1_list, scope2_list):
    x = range(len(months))
    width = 0.35
    plt.figure(figsize=(6, 3))
    plt.bar([i - width/2 for i in x], scope1_list, width=width, label='Scope 1', color='orange')
    plt.bar([i + width/2 for i in x], scope2_list, width=width, label='Scope 2', color='green')
    plt.xticks(x, months)
    plt.xlabel('Date')
    plt.ylabel('Emissions (kgCO₂)')
    plt.title('Scope 1 & 2 Emissions')
    plt.legend()
    plt.tight_layout()
    plt.savefig(GRAPH_PATH_SCOPE)
    plt.close()
