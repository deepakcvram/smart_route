import io
import csv
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generate_csv_report(route_summary: dict, alerts: list, weather: dict) -> str:
    """
    Generate a formatted CSV report containing route intelligence and detailed hotspot records.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Route Metadata Section
    writer.writerow(["# SafeRoute AI - Route Safety & Accident Hotspot Report"])
    writer.writerow(["# Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["# Origin", route_summary.get("start_label", "N/A")])
    writer.writerow(["# Destination", route_summary.get("end_label", "N/A")])
    writer.writerow(["# Corridor Distance (km)", route_summary.get("route_distance_km", 0.0)])
    writer.writerow(["# Route Safety Score", f"{route_summary.get('safety_score', 'N/A')}/100"])
    writer.writerow(["# Risk Category", route_summary.get("risk_category", "N/A")])
    writer.writerow(["# Total Hotspots", route_summary.get("total_hotspots", 0)])
    writer.writerow(["# High Risk Zones", route_summary.get("high_count", 0)])
    writer.writerow(["# Medium Risk Zones", route_summary.get("medium_count", 0)])
    writer.writerow(["# Low Risk Zones", route_summary.get("low_count", 0)])
    writer.writerow([
        "# Route Midpoint Weather",
        f"{weather.get('description', 'Clear')}, {weather.get('temp', 28):.1f} C, Wind: {weather.get('wind_speed', 0)} km/h"
    ])
    writer.writerow([])  # blank line separator

    # Hotspot Column Headers
    headers = [
        "Hotspot_Number",
        "Cluster_ID",
        "Risk_Level",
        "Distance_From_Route_Meters",
        "Latitude",
        "Longitude",
        "Historical_Accidents",
        "Fatal_Accidents",
        "Casualties",
        "Primary_Cause",
        "Peak_Hour",
        "Night_Accidents_Pct",
        "Historical_Weather",
        "Current_Weather",
        "Safety_Recommendation"
    ]
    writer.writerow(headers)

    # Data Rows
    for i, a in enumerate(alerts or []):
        row = [
            i + 1,
            a.get("cluster_id", "N/A"),
            a.get("risk_level", "N/A"),
            a.get("distance_m", "N/A"),
            a.get("hotspot_lat", "N/A"),
            a.get("hotspot_lon", "N/A"),
            a.get("total_accidents", "N/A"),
            a.get("fatal", 0),
            a.get("casualties", 0),
            a.get("top_cause", "N/A"),
            f"{a.get('peak_hour', 12):02d}:00",
            f"{a.get('night_pct', 0)}%",
            a.get("top_weather", "N/A"),
            weather.get("description", "Clear"),
            a.get("safety_recommendation", a.get("ai_desc", "Exercise caution.")),
        ]
        writer.writerow(row)

    return output.getvalue()


def generate_pdf_report(route_summary: dict, alerts: list, weather: dict) -> bytes:
    """
    Generate a professional PDF safety report using ReportLab.
    Returns bytes suitable for Streamlit download button.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    )
    section_h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1e293b"),
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0f172a"),
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        spaceBefore=12,
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("SafeRoute AI — Route Safety & Accident Hotspot Report", title_style))
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(f"Automated Road Risk Intelligence • Generated: {now_str}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=10))

    # Route Overview Table
    origin = route_summary.get("start_label", "Origin")
    dest = route_summary.get("end_label", "Destination")
    dist_km = route_summary.get("route_distance_km", 0.0)
    score = route_summary.get("safety_score", "N/A")
    cat = route_summary.get("risk_category", "MODERATE RELATIVE RISK")

    overview_data = [
        [
            Paragraph("<b>Origin:</b>", body_style), Paragraph(str(origin), body_style),
            Paragraph("<b>Destination:</b>", body_style), Paragraph(str(dest), body_style)
        ],
        [
            Paragraph("<b>Corridor Distance:</b>", body_style), Paragraph(f"{dist_km:.1f} km", body_style),
            Paragraph("<b>Safety Score:</b>", body_style), Paragraph(f"<b>{score}/100</b> ({cat})", body_style)
        ],
        [
            Paragraph("<b>Total Hotspots:</b>", body_style), Paragraph(f"{len(alerts or [])} mapped", body_style),
            Paragraph("<b>Severity Breakdown:</b>", body_style),
            Paragraph(f"{route_summary.get('high_count',0)} High • {route_summary.get('medium_count',0)} Med • {route_summary.get('low_count',0)} Low", body_style)
        ],
        [
            Paragraph("<b>Current Weather:</b>", body_style),
            Paragraph(f"{weather.get('description','Clear')} ({weather.get('temp',28):.0f}°C, Wind {weather.get('wind_speed',0):.0f} km/h)", body_style),
            Paragraph("<b>Surface Condition:</b>", body_style),
            Paragraph("Wet / Low Friction" if weather.get("is_rain") else ("Fog / Low Visibility" if weather.get("is_fog") else "Dry / Normal"), body_style)
        ],
    ]

    overview_table = Table(overview_data, colWidths=[105, 160, 105, 170])
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 12))

    # Hotspot Details Section
    story.append(Paragraph(f"Identified Accident Hotspots Along Corridor ({len(alerts or [])})", section_h2))

    if not alerts:
        story.append(Paragraph("All Clear: No historical accident hotspots were detected within 500m of this route.", body_style))
    else:
        th_data = [
            [
                Paragraph("<b>#</b>", table_cell_bold),
                Paragraph("<b>Cluster</b>", table_cell_bold),
                Paragraph("<b>Risk</b>", table_cell_bold),
                Paragraph("<b>Offset</b>", table_cell_bold),
                Paragraph("<b>Accidents</b>", table_cell_bold),
                Paragraph("<b>Fatal / Cas</b>", table_cell_bold),
                Paragraph("<b>Primary Cause</b>", table_cell_bold),
                Paragraph("<b>Peak Period</b>", table_cell_bold),
                Paragraph("<b>Safety Recommendation</b>", table_cell_bold),
            ]
        ]

        for i, a in enumerate(alerts):
            is_high = a.get("risk_level") == "HIGH"
            is_med = a.get("risk_level") == "MEDIUM"
            risk_color_hex = "#dc2626" if is_high else ("#ea580c" if is_med else "#16a34a")

            dm = a.get("distance_m", 0)
            offset_str = f"{dm}m" if dm < 1000 else f"{dm/1000:.1f}km"
            rec = a.get("safety_recommendation") or a.get("ai_desc", "Maintain safe gap and reduce speed.")

            th_data.append([
                Paragraph(str(i + 1), table_cell),
                Paragraph(f"#{a.get('cluster_id', 'N/A')}", table_cell),
                Paragraph(f"<font color='{risk_color_hex}'><b>{a.get('risk_level', 'N/A')}</b></font>", table_cell),
                Paragraph(offset_str, table_cell),
                Paragraph(str(a.get("total_accidents", "N/A")), table_cell),
                Paragraph(f"{a.get('fatal', 0)} / {a.get('casualties', 0)}", table_cell),
                Paragraph(str(a.get("top_cause", "N/A")).title(), table_cell),
                Paragraph(f"{a.get('peak_hour', 12):02d}:00", table_cell),
                Paragraph(rec, table_cell),
            ])

        hotspot_table = Table(
            th_data,
            colWidths=[18, 42, 50, 40, 48, 55, 62, 55, 170]
        )
        hotspot_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(hotspot_table)

    # Disclaimer & Methodology Note
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Important Notice:</b> The Route Safety Score and hotspot markers are heuristic indicators derived "
        "from historical accident density (DBSCAN spatial clustering) and road route alignment (OSRM). Weather data is "
        "retrieved from OpenWeatherMap at the route midpoint. This report is intended solely to enhance driver risk "
        "awareness and defensive driving. It does not constitute a guaranteed safety assessment or statistical collision forecast.",
        disclaimer_style
    ))

    doc.build(story)
    return buf.getvalue()
