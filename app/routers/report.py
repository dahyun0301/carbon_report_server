from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
import os
import datetime
from collections import defaultdict

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_pdf(file_path: str, records, company_name: str, industry: str, quota: float, start_month: str, end_month: str):
    # PDF 초기 설정
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    # 제목 및 기본 정보
    c.setFont("Helvetica-Bold", 16)
    c.drawString(180, height - 40, "탄소 배출 보고서")
    c.setFont("Helvetica", 12)
    y_cursor = height - 80
    c.drawString(50, y_cursor, f"기업명: {company_name}")
    c.drawString(300, y_cursor, f"업종: {industry}")
    y_cursor -= 20
    c.drawString(50, y_cursor, f"분석 기간: {start_month} ~ {end_month}")

    # 기간 계산 (개월 단위)
    try:
        start_dt = datetime.datetime.strptime(start_month, "%Y-%m")
        end_dt = datetime.datetime.strptime(end_month, "%Y-%m")
        months_diff = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
    except ValueError:
        months_diff = 0
    long_period = months_diff > 12

    # 데이터 집계
    scope1_total = 0.0
    scope2_total = 0.0
    total_emission = 0.0
    monthly_summary = defaultdict(float)
    yearly_summary = defaultdict(float)

    for r in records:
        # 월 정보 파싱
        try:
            rec_dt = datetime.datetime.strptime(r.month, "%Y-%m")
            month_key = r.month
            year_key = str(rec_dt.year)
        except Exception:
            month_key = r.month
            year_key = r.month.split('-')[0] if '-' in r.month else r.month

        scope1 = r.gasoline * 2.31 + r.natural_gas * 0.203
        scope2 = r.electricity * 0.417 + r.district_heating * 110
        total = round(scope1 + scope2, 2)
        scope1_total += scope1
        scope2_total += scope2
        total_emission += total
        monthly_summary[month_key] += total
        yearly_summary[year_key] += total

    # Scope 요약
    y_cursor -= 40
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y_cursor, "[Scope 배출량 요약]")
    y_cursor -= 20
    c.setFont("Helvetica", 12)
    c.drawString(50, y_cursor, f"Scope 1: {scope1_total:.2f} kgCO₂")
    y_cursor -= 20
    c.drawString(50, y_cursor, f"Scope 2: {scope2_total:.2f} kgCO₂")
    y_cursor -= 20
    c.drawString(50, y_cursor, f"총 배출량: {total_emission:.2f} kgCO₂")

    # 규제 기준 초과 여부
    y_cursor -= 40
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y_cursor, "[규제 기준 초과 여부]")
    y_cursor -= 20
    c.setFont("Helvetica", 12)
    if total_emission <= quota:
        c.drawString(50, y_cursor, f"✅ 기준 미만: 남은 배출권 {quota - total_emission:.2f} kgCO₂")
    else:
        c.drawString(50, y_cursor, f"❌ 초과: 추가 필요 {total_emission - quota:.2f} kgCO₂")

    # 차트 영역
    y_cursor -= 60
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y_cursor, "[탄소 배출량 시각화]")

    chart_height = 120
    chart_width = 300

    # 연도별 차트 (1년 초과 기간일 때만)
    if long_period and yearly_summary:
        y_cursor -= 20
        c.setFont("Helvetica", 11)
        c.drawString(50, y_cursor, "▶ 연도별 배출량")
        drawing_year = Drawing(chart_width + 50, chart_height + 30)
        bc_year = VerticalBarChart()
        bc_year.x = 0
        bc_year.y = 10
        bc_year.height = chart_height
        bc_year.width = chart_width
        bc_year.data = [list(yearly_summary.values())]
        bc_year.categoryAxis.categoryNames = list(yearly_summary.keys())
        bc_year.barWidth = 20
        bc_year.valueAxis.valueMin = 0
        bc_year.strokeColor = colors.black
        drawing_year.add(bc_year)
        drawing_year.drawOn(c, 50, y_cursor - chart_height - 10)
        y_cursor -= (chart_height + 50)

    # 월별 차트 (데이터 있을 때만)
    if monthly_summary:
        y_cursor -= 20
        c.setFont("Helvetica", 11)
        c.drawString(50, y_cursor, "▶ 월별 배출량")
        drawing_month = Drawing(chart_width + 50, chart_height + 30)
        bc_month = VerticalBarChart()
        bc_month.x = 0
        bc_month.y = 10
        bc_month.height = chart_height
        bc_month.width = chart_width
        bc_month.data = [list(monthly_summary.values())]
        bc_month.categoryAxis.categoryNames = list(monthly_summary.keys())
        bc_month.barWidth = 10
        bc_month.valueAxis.valueMin = 0
        bc_month.strokeColor = colors.black
        drawing_month.add(bc_month)
        drawing_month.drawOn(c, 50, y_cursor - chart_height - 10)
        y_cursor -= (chart_height + 50)
    else:
        y_cursor -= 20
        c.setFont("Helvetica", 11)
        c.drawString(50, y_cursor, "▶ 월별 배출량 데이터가 없습니다.")
        y_cursor -= 20

    # 피드백
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y_cursor, "[피드백]")
    c.setFont("Helvetica", 11)
    y_cursor -= 20
    c.drawString(50, y_cursor, f"• 총 배출량: {total_emission:.2f} kgCO₂ 요약 완료.")
    y_cursor -= 15
    
    # Scope 비율 계산
    if total_emission > 0:
        scope1_pct = scope1_total / total_emission * 100
        scope2_pct = scope2_total / total_emission * 100
    else:
        scope1_pct = scope2_pct = 0.0
    c.drawString(50, y_cursor, f"• Scope 1 비중: {scope1_pct:.1f}%, Scope 2 비중: {scope2_pct:.1f}%.")
    y_cursor -= 15
    c.drawString(50, y_cursor, "• 비효율 공정: 에너지 사용량 높은 항목 점검 권장.")

    c.save()


@router.get("/report-preview")
def preview_report(
    db: Session = Depends(get_db),
    company_name: str = "AI Tech",
    industry: str = "제조업",
    quota: float = 50000.0,
    start: str = "2024-01",
    end: str = "2024-12"
):
    # PDF 파일 경로 설정
    file_path = "static/preview_report.pdf"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # DB 데이터 로드
    records = db.query(EmissionRecord).all()

    # PDF 생성
    create_pdf(
        file_path=file_path,
        records=records,
        company_name=company_name,
        industry=industry,
        quota=quota,
        start_month=start,
        end_month=end
    )

    # 브라우저 inline 표시
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename="탄소_배출_보고서.pdf"
    )
