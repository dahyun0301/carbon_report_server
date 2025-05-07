from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas          # type: ignore
from reportlab.lib.pagesizes import letter   # type: ignore
from reportlab.lib.utils import ImageReader  # type: ignore
import io
import matplotlib.pyplot as plt               # type: ignore

from app.db import get_db
from app.main import templates
from app.crud import (
    get_emission_summary,
    get_trade_eligibility,
    get_monthly_emissions_data,
    get_eligibility_feedback
)

router = APIRouter()

@router.get("/report")
async def read_report(request: Request, db: Session = Depends(get_db)):
    summary = get_emission_summary(db)
    eligibility = get_trade_eligibility(summary)
    monthly_data = get_monthly_emissions_data(db)
    return templates.TemplateResponse(
        "report.html",
        {"request": request, "summary": summary, "eligibility": eligibility, "monthly_data": monthly_data}
    )

@router.get("/report/pdf")
async def download_report(db: Session = Depends(get_db)):
    summary = get_emission_summary(db)
    eligibility = get_trade_eligibility(summary)
    monthly_data = get_monthly_emissions_data(db)
    feedback = get_eligibility_feedback(summary, eligibility)

    # Extract month/emission lists
    try:
        months = [row["month"] for row in monthly_data]
        emissions = [row["emission"] for row in monthly_data]
    except Exception:
        months = [row.month for row in monthly_data]
        emissions = [row.emission for row in monthly_data]

    # Generate chart
    chart_buf = io.BytesIO()
    plt.figure()
    plt.plot(months, emissions)
    plt.title("Monthly Carbon Emissions")
    plt.xlabel("Month")
    plt.ylabel("Emissions")
    plt.tight_layout()
    plt.savefig(chart_buf, format="PNG")
    plt.close()
    chart_buf.seek(0)

    # Create PDF
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Carbon Emission Report")

    # Summary section
    text = c.beginText(50, 720)
    text.setFont("Helvetica", 12)
    text.textLine(f"Scope 1 Emissions: {summary.scope1}")
    text.textLine(f"Scope 2 Emissions: {summary.scope2}")
    text.textLine(f"Scope 3 Emissions: {summary.scope3}")
    text.textLine(f"Trading Eligibility: {eligibility}")
    c.drawText(text)

    # Insert chart image
    image = ImageReader(chart_buf)
    c.drawImage(image, 50, 350, width=500, height=300)

    # Feedback section
    y = 330
    for line in feedback.splitlines():
        c.drawString(50, y, line)
        y -= 15

    c.showPage()
    c.save()
    pdf_buf.seek(0)

    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=carbon_report.pdf"}
    )

# Requirements: reportlab, matplotlib
# Install with: pip install reportlab matplotlib
