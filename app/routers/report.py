from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
import os
import datetime
from collections import defaultdict
from urllib.parse import quote

# 프로젝트 루트가 carbon_report_server/app/routers/report.py라면
BASE = Path(__file__).resolve().parent.parent  # -> carbon_report_server/app
FONT_PATH = BASE / "static" / "fonts" / "NanumHumanBold.ttf"

pdfmetrics.registerFont(
    TTFont("NanumHumBold", str(FONT_PATH))
)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_pdf(file_path: str,
               records,
               company_name: str,
               industry: str,
               quota: float,
               start_month: str,
               end_month: str):
    # 1) Canvas 생성 및 페이지 크기
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    # 2) 기간 계산
    try:
        sd = datetime.datetime.strptime(start_month, "%Y-%m")
        ed = datetime.datetime.strptime(end_month,   "%Y-%m")
        months_diff = (ed.year - sd.year) * 12 + (ed.month - sd.month)
    except:
        months_diff = 0
    long_period = months_diff > 12

    # 3) 합계 변수 초기화
    scope1_total   = 0.0
    scope2_total   = 0.0
    total_emission = 0.0
    monthly_summary = defaultdict(float)
    yearly_summary  = defaultdict(float)

    # 4) 레코드 순회하며 누적 계산
    for r in records:
        try:
            rec_dt = datetime.datetime.strptime(r.month, "%Y-%m")
            ykey = str(rec_dt.year)
        except:
            ykey = r.month.split("-")[0] if "-" in r.month else r.month
        mkey = r.month

        s1 = r.gasoline * 2.31 + r.natural_gas * 0.203
        s2 = r.electricity * 0.417 + r.district_heating * 110
        t  = round(s1 + s2, 2)

        scope1_total   += s1
        scope2_total   += s2
        total_emission += t

        monthly_summary[mkey] += t
        yearly_summary[ykey]  += t

    # 5) 글꼴 설정 (NanumHumBold로 등록했을 경우)
    c.setFont("NanumHumBold", 16)
    c.drawString(180, height - 40, "탄소 배출 보고서")

    # 6) 기본 정보 출력
    y = height - 80
    c.setFont("NanumHumBold", 12)
    c.drawString(50, y, f"기업명: {company_name}")
    c.drawString(300, y, f"업종: {industry}")
    y -= 20
    c.drawString(50, y, f"분석 기간: {start_month} ~ {end_month}")

    # 7) Scope 요약 출력
    y -= 40
    c.setFont("NanumHumBold", 13)
    c.drawString(50, y, "[Scope 배출량 요약]")
    y -= 20
    c.setFont("NanumHumBold", 11)
    c.drawString(50, y, f"Scope 1: {scope1_total:.2f} kgCO₂")
    y -= 20
    c.drawString(50, y, f"Scope 2: {scope2_total:.2f} kgCO₂")
    y -= 20
    c.drawString(50, y, f"총 배출량: {total_emission:.2f} kgCO₂")

    # 8) 규제 기준 초과 여부
    y -= 40
    c.setFont("NanumHumBold", 13)
    c.drawString(50, y, "[규제 기준 초과 여부]")
    y -= 20
    c.setFont("NanumHumBold", 11)
    if total_emission <= quota:
        c.drawString(50, y, f"✅ 기준 미만: 남은 배출권 {quota - total_emission:.2f} kgCO₂")
    else:
        c.drawString(50, y, f"❌ 초과: 추가 필요 {total_emission - quota:.2f} kgCO₂")

    # 9) 차트 그리기
    y -= 60
    c.setFont("NanumHumBold", 13)
    c.drawString(50, y, "[탄소 배출량 시각화]")
    chart_h, chart_w = 120, 300

    # 연도별 (12월 초과 시)
    if long_period and yearly_summary:
        y -= 20
        c.setFont("NanumHumBold", 11)
        c.drawString(50, y, "▶ 연도별 배출량")
        dy = Drawing(chart_w + 50, chart_h + 30)
        bc = VerticalBarChart()
        bc.x, bc.y = 0, 10
        bc.height, bc.width = chart_h, chart_w
        bc.data = [list(yearly_summary.values())]
        bc.categoryAxis.categoryNames = list(yearly_summary.keys())
        bc.barWidth = 20
        bc.valueAxis.valueMin = 0
        bc.strokeColor = colors.black
        dy.add(bc)
        dy.drawOn(c, 50, y - chart_h - 10)
        y -= (chart_h + 50)

    # 월별
    if monthly_summary:
        y -= 20
        c.setFont("NanumHumBold", 11)
        c.drawString(50, y, "▶ 월별 배출량")
        dm = Drawing(chart_w + 50, chart_h + 30)
        bcm = VerticalBarChart()
        bcm.x, bcm.y = 0, 10
        bcm.height, bcm.width = chart_h, chart_w
        bcm.data = [list(monthly_summary.values())]
        bcm.categoryAxis.categoryNames = list(monthly_summary.keys())
        bcm.barWidth = 10
        bcm.valueAxis.valueMin = 0
        bcm.strokeColor = colors.black
        dm.add(bcm)
        dm.drawOn(c, 50, y - chart_h - 10)

    # 10) 피드백
    y -= (chart_h + 60)
    c.setFont("NanumHumBold", 13)
    c.drawString(50, y, "[피드백]")
    y -= 20
    c.setFont("NanumHumBold", 11)
    c.drawString(50, y, f"• 총 배출량: {total_emission:.2f} kgCO₂ 요약 완료.")
    y -= 15
    if total_emission > 0:
        pct1 = scope1_total/total_emission*100
        pct2 = scope2_total/total_emission*100
    else:
        pct1 = pct2 = 0
    c.drawString(50, y, f"• Scope 1 비중: {pct1:.1f}%, Scope 2 비중: {pct2:.1f}%")
    y -= 15
    c.drawString(50, y, "• 비효율 공정: 에너지 사용량 높은 항목 점검 권장.")

    # 11) PDF 저장
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

    filename = "탄소_배출_보고서.pdf"
    disp = f"inline; filename*=UTF-8''{quote(filename)}"
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": disp},
    )


@router.get("/report-download")
def download_report(
    db: Session = Depends(get_db),
    company_name: str = "AI Tech",
    industry: str = "제조업",
    quota: float = 50000.0,
    start: str = "2024-01",
    end: str = "2024-12"
):
    # 동일한 PDF 생성 로직 재사용
    file_path = "static/preview_report.pdf"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    records = db.query(EmissionRecord).all()
    create_pdf(
        file_path=file_path,
        records=records,
        company_name=company_name,
        industry=industry,
        quota=quota,
        start_month=start,
        end_month=end
    )

    # 다운로드용 Content-Disposition: attachment
    filename = "탄소_배출_보고서.pdf"
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )


templates = Jinja2Templates(directory="app/templates")

@router.get("/report", response_class=HTMLResponse)
def report_page(
    request: Request,
    company_name: str = "AI Tech",
    industry: str = "제조업",
    quota: float = 50000.0,
    start: str = "2024-01",
    end: str = "2024-12"
):
    """
    1) report.html 템플릿을 렌더링해서 PDF 미리보기(iframe)와
       다운로드 버튼을 같이 보여줍니다.
    2) 실제 PDF는 /report-preview 와 /report-download 엔드포인트를 사용.
    """
    return templates.TemplateResponse("report.html", {
        "request": request,
        "company_name": company_name,
        "industry": industry,
        "quota": quota,
        "start": start,
        "end": end
    })