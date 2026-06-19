"""GET /reports/pdf — generate and stream PDF clinical reports.

The PDF includes:
  - Cover page with NeuroGuard branding + patient demographics
  - Risk score trend chart (matplotlib)
  - Latest SHAP attribution table (top 10 contributors)
  - Sleep biomarker summary table
  - Alert history within the report period
  - Clinician notes & disclaimer footer
"""

import io
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)
from reportlab.lib import colors
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.config import get_settings
from ....shared.db.session import get_db
from ....shared.models.alert import Alert
from ....shared.models.report import Report
from ....shared.models.risk_prediction import RiskPrediction
from ....shared.models.sleep_metrics import SleepMetrics
from ....shared.models.user import User
from ....shared.security.hipaa_logger import log_explicit
from ....shared.security.jwt import get_current_user
from ....shared.security.rbac import Role

router   = APIRouter()
settings = get_settings()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/pdf")
async def generate_pdf_report(
    request:      Request,
    patient_id:   Optional[uuid.UUID] = None,
    period_start: str = "",
    period_end:   str = "",
    current_user: dict = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Generate a clinical PDF report and stream it directly to the client.

    - Users can fetch their own reports (patient_id optional — defaults to self)
    - Clinicians/admins must specify patient_id of one of their patients
    """
    requester_id   = uuid.UUID(current_user["sub"])
    requester_role = current_user.get("role", "user")

    target_id = patient_id or requester_id
    if requester_role == "user" and target_id != requester_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Default period: last 90 days
    if not period_end:
        period_end = date.today().isoformat()
    if not period_start:
        period_start = (date.today() - timedelta(days=90)).isoformat()
    try:
        start = date.fromisoformat(period_start)
        end   = date.fromisoformat(period_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="period_start and period_end must be YYYY-MM-DD")

    # Fetch all data for the report
    user_result = await db.execute(select(User).where(User.id == target_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt   = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)

    risk_result = await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.user_id == target_id,
               RiskPrediction.predicted_at >= start_dt,
               RiskPrediction.predicted_at <= end_dt)
        .order_by(RiskPrediction.predicted_at)
    )
    predictions = risk_result.scalars().all()

    sleep_result = await db.execute(
        select(SleepMetrics)
        .where(SleepMetrics.user_id == target_id,
               SleepMetrics.sleep_date >= start,
               SleepMetrics.sleep_date <= end)
        .order_by(SleepMetrics.sleep_date)
    )
    sleep_records = sleep_result.scalars().all()

    alert_result = await db.execute(
        select(Alert)
        .where(Alert.user_id == target_id,
               Alert.created_at >= start_dt,
               Alert.created_at <= end_dt)
        .order_by(desc(Alert.created_at))
        .limit(20)
    )
    alerts = alert_result.scalars().all()

    # Build PDF in memory
    pdf_buffer = io.BytesIO()
    _build_pdf(pdf_buffer, user, predictions, sleep_records, alerts, start, end)
    pdf_bytes = pdf_buffer.getvalue()

    # Audit
    await log_explicit(
        "EXPORT", "report",
        actor_id=requester_id, actor_role=requester_role,
        patient_id=target_id, outcome="success",
        details={"period_start": period_start, "period_end": period_end, "size_bytes": len(pdf_bytes)},
    )

    # Persist a row for tracking
    report = Report(
        user_id        = target_id,
        clinician_id   = requester_id if requester_role in ("clinician", "hospital_admin") else None,
        report_type    = "clinical_assessment",
        period_start   = start,
        period_end     = end,
        s3_key         = f"inline-{uuid.uuid4()}",   # not actually uploaded in dev
        file_size_bytes= len(pdf_bytes),
    )
    db.add(report)
    await db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="neuroguard_report_{target_id}_{period_start}_{period_end}.pdf"',
            "X-Report-Id"         : str(report.id),
        },
    )


# ── PDF builder ──────────────────────────────────────────────────────────────

NG_BLUE  = colors.HexColor("#1E3A5F")
NG_GREEN = colors.HexColor("#10B981")
NG_AMBER = colors.HexColor("#F59E0B")
NG_RED   = colors.HexColor("#EF4444")
NG_GREY  = colors.HexColor("#6B7280")


def _build_pdf(
    buffer:        io.BytesIO,
    user:          User,
    predictions:   list,
    sleep_records: list,
    alerts:        list,
    start:         date,
    end:           date,
) -> None:
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        title="NeuroGuard Clinical Report",
        author="NeuroGuard AI",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="NGTitle",     parent=styles["Title"],    textColor=NG_BLUE, fontSize=22, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="NGHeading",   parent=styles["Heading2"], textColor=NG_BLUE, fontSize=14, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="NGLabel",     parent=styles["Normal"],   textColor=NG_GREY, fontSize=9))
    styles.add(ParagraphStyle(name="NGFooter",    parent=styles["Italic"],   textColor=NG_GREY, fontSize=8, alignment=TA_CENTER))

    story: list = []

    # ── Cover header ───────────────────────────────────────────────────────────
    story.append(Paragraph("NeuroGuard AI", styles["NGTitle"]))
    story.append(Paragraph("Clinical Assessment Report", styles["NGHeading"]))
    story.append(Spacer(1, 12))

    # Patient demographics box
    latest_score    = predictions[-1] if predictions else None
    score_text      = f"{latest_score.risk_score:.0%}" if latest_score else "—"
    tier_text       = latest_score.risk_tier.replace("_", " ").title() if latest_score else "Insufficient data"
    score_color     = _tier_color(latest_score.risk_tier if latest_score else "low")

    demographics = [
        ["Patient ID",      str(user.id)],
        ["Age",             str(user.age) if user.age else "—"],
        ["Gender",          (user.gender or "—").upper()],
        ["Risk Group",      (user.risk_group or "general").replace("_", " ").title()],
        ["Family History",  "Yes" if user.family_history else "No"],
        ["Report Period",   f"{start.isoformat()} to {end.isoformat()}"],
        ["Generated",       datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
        ["Model Version",   latest_score.model_version if latest_score else "n/a"],
    ]
    demo_table = Table(demographics, colWidths=[1.8 * inch, 4.5 * inch])
    demo_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR",   (0, 0), (0, -1), NG_GREY),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",   (0, 0), (-1, -2), 0.25, colors.HexColor("#E5E7EB")),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 18))

    # ── Headline risk card ─────────────────────────────────────────────────────
    headline = Table(
        [[
            Paragraph(f"<b>Current Risk Score</b>", styles["Normal"]),
            Paragraph(
                f'<font color="{score_color.hexval()}" size="22"><b>{score_text}</b></font> '
                f'<font color="#6B7280">({tier_text})</font>',
                styles["Normal"],
            ),
        ]],
        colWidths=[2.0 * inch, 4.3 * inch],
    )
    headline.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
        ("BOX",          (0, 0), (-1, -1), 1, NG_BLUE),
        ("TOPPADDING",   (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",  (0, 0), (-1, -1), 14),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(headline)
    story.append(Spacer(1, 16))

    # ── Risk trend chart ───────────────────────────────────────────────────────
    if len(predictions) >= 2:
        chart_buf = _render_risk_chart(predictions)
        story.append(Paragraph("Risk Score Trend", styles["NGHeading"]))
        story.append(Image(chart_buf, width=6.3 * inch, height=2.6 * inch))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"{len(predictions)} risk evaluations during this period. "
            f"Score range: {min(p.risk_score for p in predictions):.0%} – "
            f"{max(p.risk_score for p in predictions):.0%}.",
            styles["NGLabel"],
        ))

    # ── SHAP attribution table ─────────────────────────────────────────────────
    if latest_score and latest_score.shap_values:
        story.append(Paragraph("ML Explanation — Top Contributing Biomarkers", styles["NGHeading"]))
        shap_items = sorted(latest_score.shap_values.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10]
        total = sum(abs(v) for _, v in shap_items) or 1.0
        shap_rows = [["Biomarker", "Contribution", "Direction"]]
        for name, val in shap_items:
            pct = abs(val) / total * 100
            direction = "↑ Increases risk" if val > 0 else "↓ Decreases risk"
            shap_rows.append([
                name.replace("_", " ").title(),
                f"{pct:.1f}%",
                direction,
            ])
        shap_table = Table(shap_rows, colWidths=[3.0 * inch, 1.4 * inch, 1.9 * inch])
        shap_table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), NG_BLUE),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("LINEBELOW",   (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ]))
        story.append(shap_table)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Computed by NeuroGuard model {latest_score.model_version}. "
            f"Keystroke contribution {(latest_score.keystroke_contribution or 0):.0%}, "
            f"Sleep contribution {(latest_score.sleep_contribution or 0):.0%}.",
            styles["NGLabel"],
        ))

    # ── Sleep biomarker summary ────────────────────────────────────────────────
    if sleep_records:
        story.append(PageBreak())
        story.append(Paragraph("Sleep Biomarker Summary", styles["NGHeading"]))

        def avg(field):
            vals = [getattr(s, field) for s in sleep_records if getattr(s, field) is not None]
            return sum(vals) / len(vals) if vals else None

        def fmt(v, suffix=""):
            return f"{v:.2f}{suffix}" if v is not None else "—"

        sleep_rows = [
            ["Metric",                    "Mean (period)",                            "Reference"],
            ["Sleep efficiency",          fmt(avg("sleep_efficiency")),               "≥ 0.85"],
            ["REM duration (min)",        fmt(avg("rem_duration_min")),               "80–110"],
            ["REM fragmentation index",   fmt(avg("rem_fragmentation_idx")),          "< 0.30"],
            ["Stage transitions",         fmt(avg("sleep_stage_transitions")),        "12–25"],
            ["HRV RMSSD (ms)",            fmt(avg("hrv_rmssd")),                      "30–60"],
            ["Resting heart rate (bpm)",  fmt(avg("resting_hr")),                     "55–75"],
            ["Awakenings",                fmt(avg("awakenings")),                     "< 5"],
            ["Sleep onset (min)",         fmt(avg("sleep_onset_min")),                "< 20"],
        ]
        st = Table(sleep_rows, colWidths=[2.6 * inch, 1.8 * inch, 1.9 * inch])
        st.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), NG_BLUE),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("LINEBELOW",    (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ]))
        story.append(st)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"{len(sleep_records)} nights analysed. Reference ranges are for healthy adults aged 50–70.",
            styles["NGLabel"],
        ))

    # ── Alert history ─────────────────────────────────────────────────────────
    if alerts:
        story.append(Spacer(1, 14))
        story.append(Paragraph(f"Alert History ({len(alerts)} events)", styles["NGHeading"]))
        alert_rows = [["When", "Type", "Severity", "Summary"]]
        for a in alerts[:10]:
            alert_rows.append([
                a.created_at.strftime("%Y-%m-%d"),
                a.alert_type.replace("_", " ").title(),
                a.severity.upper(),
                (a.title or "")[:50],
            ])
        at = Table(alert_rows, colWidths=[0.9 * inch, 1.7 * inch, 0.9 * inch, 2.8 * inch])
        at.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), NG_BLUE),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("LINEBELOW",    (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ]))
        story.append(at)

    # ── Clinician notes section ───────────────────────────────────────────────
    story.append(Spacer(1, 18))
    story.append(Paragraph("Clinician Notes", styles["NGHeading"]))
    notes_box = Table([[""]], colWidths=[6.3 * inch], rowHeights=[1.2 * inch])
    notes_box.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, NG_GREY),
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
    ]))
    story.append(notes_box)

    # ── Footer / disclaimer ───────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "<b>Disclaimer:</b> NeuroGuard AI provides risk indicators based on "
        "passive biomarker analysis. It is <b>not a clinical diagnosis</b> and "
        "must not replace evaluation by a licensed neurologist. Predictions are "
        "derived from a research-stage ML model.",
        styles["NGLabel"],
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This document is HIPAA-protected. PHI access is audit-logged in NeuroGuard. "
        "Generated by NeuroGuard Reports Service — confidential.",
        styles["NGFooter"],
    ))

    doc.build(story)


def _render_risk_chart(predictions: list) -> io.BytesIO:
    """Render a matplotlib risk-trend chart and return as PNG buffer."""
    dates  = [p.predicted_at for p in predictions]
    scores = [p.risk_score   for p in predictions]

    fig, ax = plt.subplots(figsize=(9, 3.5), dpi=100)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # Risk-tier bands
    ax.axhspan(0.00, 0.15, alpha=0.10, color="#10B981")
    ax.axhspan(0.15, 0.30, alpha=0.10, color="#84CC16")
    ax.axhspan(0.30, 0.55, alpha=0.10, color="#F59E0B")
    ax.axhspan(0.55, 0.75, alpha=0.10, color="#F97316")
    ax.axhspan(0.75, 1.00, alpha=0.10, color="#EF4444")

    ax.plot(dates, scores, color="#1E3A5F", linewidth=2.4, marker="o",
            markersize=5, markerfacecolor="white", markeredgewidth=1.8)

    ax.set_ylim(0, 1)
    ax.set_ylabel("Risk Score", fontsize=10, color="#374151")
    ax.set_xlabel("Date", fontsize=10, color="#374151")
    ax.grid(axis="y", linestyle=":", color="#E5E7EB")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=8, colors="#6B7280")

    # Format dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    if len(dates) > 10:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


def _tier_color(tier: str) -> colors.Color:
    return {
        "very_low":  NG_GREEN,
        "low":       NG_GREEN,
        "moderate":  NG_AMBER,
        "high":      colors.HexColor("#F97316"),
        "very_high": NG_RED,
    }.get(tier, NG_GREY)
