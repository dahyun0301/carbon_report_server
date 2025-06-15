from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import EmissionRecord, ReportInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import textwrap
import os

from dotenv import load_dotenv
from openai import OpenAI

# 템플릿 및 라우터 설정
router = APIRouter(prefix="/report", tags=["report"])
templates = Jinja2Templates(directory="templates")

# 환경변수 로드 및 OpenAI 클라이언트 초기화
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")
client = OpenAI(api_key=api_key)

# 폰트 및 파일 경로 설정
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

@router.get("/view", response_class=HTMLResponse)
def report_page(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return templates.TemplateResponse("report.html", {"request": request})

@router.get("/preview")
def report_preview():
    return FileResponse(PDF_PATH, media_type="application/pdf")

@router.get("/download")
def report_download():
    return FileResponse(PDF_PATH, media_type="application/pdf", filename="carbon_report.pdf")

@router.get("/generate")
def generate_pdf_report(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    info = db.query(ReportInfo).filter(ReportInfo.user_id == user_id).order_by(ReportInfo.id.desc()).first()
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

    total_sum = sum(total_emissions)
    s1_sum = sum(scope1_list)
    s2_sum = sum(scope2_list)
    remaining = round(info.allowance - total_sum, 2)

    generate_total_graph(months, total_emissions)
    generate_scope_graph(months, scope1_list, scope2_list)

    # GPT 피드백 요청
    prompt = (
        f"기업명: {info.company}\n"
        f"분석 기간: {info.start_month}~{info.end_month}\n"
        f"Scope1 배출량: {round(s1_sum, 2)} kgCO₂\n"
        f"Scope2 배출량: {round(s2_sum, 2)} kgCO₂\n"
        f"총 배출량: {round(total_sum, 2)} kgCO₂\n"
        f"배출 허용량 대비 차이: {remaining} kgCO₂\n"
        f"월별 총배출량: {dict(zip(months, [round(e, 2) for e in total_emissions]))}\n\n"
        "위 정보를 바탕으로 다음 조건을 만족하는 6~8줄 이내의 간결한 전문가 피드백을 작성해 주세요:\n"
        "1. 배출량 추이를 간단히 설명하고 가장 높은 달을 지목해 주세요.\n"
        "2. 해당 월의 배출 증가 원인을 추정해 주세요 (계절, 설비, 물류, 이벤트 등 다양하게).\n"
        "3. Scope1과 Scope2 중 주된 원인을 간단히 짚어 주세요.\n"
        "4. 배출 감축을 위한 구체적 방안 1~2개 제안해 주세요.\n"
        "5. 전체적으로 어떤 개선 방향이 필요한지 간결하게 마무리해 주세요.\n"
        "각 문장은 줄바꿈을 위해 문장 끝에 `\\n`을 포함해 주세요."
    )
    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 기업의 월별 탄소배출 데이터를 분석하고 감축 전략을 제안하는 지속가능경영 전문가입니다. 데이터를 기반으로 인사이트와 실천 가능한 조언을 제공해 주세요."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    feedback_text = res.choices[0].message.content.strip()

    # PDF 작성
    c = canvas.Canvas(PDF_PATH, pagesize=A4)
    c.setFont(FONT_NAME, 14)
    c.drawCentredString(300, 800, "탄소 배출 보고서")
    c.setFont(FONT_NAME, 10)
    c.drawString(50, 770, f"기업: {info.company}")
    c.drawString(300, 770, f"기간: {info.start_month}~{info.end_month}")

    c.drawString(50, 740, "[Scope 요약]")
    c.drawString(70, 725, f"Scope1: {round(s1_sum,2)} kgCO₂")
    c.drawString(70, 710, f"Scope2: {round(s2_sum,2)} kgCO₂")
    c.drawString(70, 695, f"총배출: {round(total_sum,2)} kgCO₂")

    c.drawString(50, 670, "[규제 여부]")
    if remaining < 0:
        c.drawString(70, 655, f"기준초과: {abs(remaining)} kgCO₂")
    else:
        c.drawString(70, 655, f"기준미만: {remaining} kgCO₂")

    c.drawString(50, 620, "[총배출 그래프]")
    c.drawImage(ImageReader(GRAPH_PATH_TOTAL), 50, 410, width=500, height=160)
    c.drawString(50, 390, "[Scope1 & 2 그래프]")
    c.drawImage(ImageReader(GRAPH_PATH_SCOPE), 50, 210, width=500, height=160)

    # GPT 피드백 삽입
    c.drawString(50, 180, "[피드백]")
    lines = feedback_text.replace('\\n', '\n').split('\n')

    text_obj = c.beginText(50, 165)
    text_obj.setFont(FONT_NAME, 10)

    for line in lines:
        wrapped = textwrap.wrap(line.strip(), width=80)
        for subline in wrapped:
            text_obj.textLine(subline)
    c.drawText(text_obj)

    c.save()
    return {"message": "PDF generated successfully", "feedback": feedback_text}


def generate_total_graph(months, emissions):
    plt.figure(figsize=(6, 3))
    plt.bar(months, emissions)
    plt.xlabel('Date')
    plt.ylabel('Emissions (kgCO₂)')
    plt.title('Total Emissions')
    plt.xticks(rotation=90, fontsize=8)
    plt.tight_layout()
    plt.savefig(GRAPH_PATH_TOTAL)
    plt.close()


def generate_scope_graph(months, scope1_list, scope2_list):
    x = range(len(months))
    w = 0.35
    plt.figure(figsize=(6, 3))
    plt.bar([i-w/2 for i in x], scope1_list, w)
    plt.bar([i+w/2 for i in x], scope2_list, w)
    plt.xticks(x, months, rotation=90, fontsize=8)
    plt.xlabel('Date')
    plt.ylabel('Emissions (kgCO₂)')
    plt.title('Scope 1 & 2 Emissions')
    plt.legend(['Scope 1', 'Scope 2'])
    plt.tight_layout()
    plt.savefig(GRAPH_PATH_SCOPE)
    plt.close()
