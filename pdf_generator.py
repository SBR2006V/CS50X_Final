"""
Smart Routine Generator - PDF Generation Module
CS50x Final Project

Generates professional, printable, landscape timetable routines for student sections
using ReportLab. Formats clean timetable grids with word-wrapped subject names, codes,
and teacher names.
"""

import io
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_section_timetable_pdf(
    section_name: str,
    entries: list[dict[str, Any]] | list[Any],
    days: list[str],
    periods: list[int],
    page_compression: int = 0,
) -> io.BytesIO:
    """
    Generate an in-memory PDF timetable document for a given section.

    Args:
        section_name: Display name of the section (e.g. 'CSE-A').
        entries: List of timetable entry mappings containing 'day_of_week',
                 'period', 'subject_code', 'subject_name', and 'teacher_name'.
        days: Ordered list of working weekdays (e.g. Monday-Friday).
        periods: Ordered list of period numbers (e.g. 1-6).
        page_compression: ReportLab compression flag (0 for uncompressed, 1 for compressed).

    Returns:
        io.BytesIO stream positioned at 0 containing the generated PDF binary data.
    """
    buffer = io.BytesIO()

    # Landscape letter gives 792 x 612 pt. With 36 pt margins, printable width is 720 pt.
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=32,
        pageCompression=page_compression,
    )

    styles = getSampleStyleSheet()

    # Typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=1,  # Center
        textColor=colors.HexColor("#1e3a8a"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#64748b"),
    )
    header_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        alignment=1,
        textColor=colors.white,
    )
    day_style = ParagraphStyle(
        "DayStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#1e293b"),
    )
    slot_style = ParagraphStyle(
        "SlotStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        alignment=1,
    )
    free_style = ParagraphStyle(
        "FreeStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor("#94a3b8"),
    )
    footer_style = ParagraphStyle(
        "DocFooter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor("#94a3b8"),
    )

    # Build a lookup grid: day -> period -> slot dictionary
    grid: dict[str, dict[int, Any]] = {day: {p: None for p in periods} for day in days}
    for row in entries:
        d = row["day_of_week"]
        p = row["period"]
        if d in grid and p in grid[d]:
            grid[d][p] = {
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "teacher_name": row["teacher_name"],
            }

    # Construct table data
    table_data = [
        [Paragraph("<b>Day / Period</b>", header_style)]
        + [Paragraph(f"<b>Period {p}</b>", header_style) for p in periods]
    ]

    for day in days:
        row_cells = [Paragraph(f"<b>{escape(day)}</b>", day_style)]
        for p in periods:
            slot = grid[day][p]
            if slot:
                code_esc = escape(str(slot["subject_code"]))
                name_esc = escape(str(slot["subject_name"]))
                teacher_esc = escape(str(slot["teacher_name"]))
                cell_html = (
                    f'<b><font color="#1d4ed8" size=8.5>{code_esc}</font></b><br/>'
                    f'<font size=7 color="#475569">{name_esc}</font><br/>'
                    f'<font size=7.5 color="#1e293b"><b>{teacher_esc}</b></font>'
                )
                row_cells.append(Paragraph(cell_html, slot_style))
            else:
                row_cells.append(Paragraph("&mdash; Free &mdash;", free_style))
        table_data.append(row_cells)

    # 1 Day col (84 pt) + 6 Period cols (106 pt each) = 720 pt exact printable width
    col_widths = [84] + [106] * len(periods)
    timetable_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    timetable_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f8fafc")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])
    )

    safe_section_name = escape(section_name)
    elements: list[Flowable] = [
        Paragraph("<b>Smart Routine Generator</b>", title_style),
        Spacer(1, 4),
        Paragraph(
            f"Section: <b>{safe_section_name}</b> &bull; Weekly Timetable Routine",
            subtitle_style,
        ),
        Spacer(1, 3),
        Paragraph(
            "Monday &ndash; Friday &bull; 6 Periods / Day &bull; Automated Clash-Free Routine",
            meta_style,
        ),
        Spacer(1, 14),
        timetable_table,
        Spacer(1, 12),
        Paragraph(
            "Smart Routine Generator &bull; CS50x Final Project &bull; Clash-Free Timetable Routine",
            footer_style,
        ),
    ]

    doc.build(elements)
    buffer.seek(0)
    return buffer
