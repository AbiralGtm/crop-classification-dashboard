"""Downloadable report generation: PDF summary, CSV of per-class stats, and
GeoTIFF of the classified raster.

The GeoTIFF isn't generated or stored by this router directly -- the
classification job (app/ml/inference.py) already asks Earth Engine for a
getDownloadURL at classification time (the same pattern used for the
thumbnail PNG) and saves that URL in the stored result. This endpoint just
redirects to it. For AOIs too large for that synchronous download to work,
a future version would need to move to an async
Export.image.toDrive/toCloudStorage task instead.
"""
import csv
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app import store

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{aoi_id}/geotiff")
def export_geotiff(aoi_id: str) -> RedirectResponse:
    job = store.get_job(aoi_id)
    if job is None or not job.get("result"):
        raise HTTPException(status_code=404, detail="No results available for this AOI")

    geotiff_url = job["result"].get("geotiff_url")
    if not geotiff_url:
        raise HTTPException(
            status_code=404,
            detail="GeoTIFF was not generated for this AOI (it may be too large, or classification predates this feature).",
        )
    return RedirectResponse(url=geotiff_url)


@router.get("/{aoi_id}/csv")
def export_csv(aoi_id: str) -> StreamingResponse:
    job = store.get_job(aoi_id)
    if job is None or not job.get("result"):
        raise HTTPException(status_code=404, detail="No results available for this AOI")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["class_name", "area_hectares"])
    for row in job["result"]["class_stats"]:
        writer.writerow([row["class_name"], row["area_hectares"]])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=aoi_{aoi_id}_stats.csv"},
    )


@router.get("/{aoi_id}/pdf")
def export_pdf(aoi_id: str) -> StreamingResponse:
    job = store.get_job(aoi_id)
    if job is None or not job.get("result"):
        raise HTTPException(status_code=404, detail="No results available for this AOI")

    request = job["request"]
    class_stats = job["result"]["class_stats"]

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, f"Crop Classification Report — {request.name}")
    y -= 24
    c.setFont("Helvetica", 10)
    c.drawString(72, y, f"Date range: {request.start_date} to {request.end_date}")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Class")
    c.drawString(300, y, "Area (hectares)")
    y -= 16
    c.setFont("Helvetica", 11)
    total_ha = sum(row["area_hectares"] for row in class_stats)
    for row in class_stats:
        c.drawString(72, y, row["class_name"])
        c.drawString(300, y, str(row["area_hectares"]))
        y -= 16
        if y < 72:
            c.showPage()
            y = height - 72
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(72, y, f"Total area: {round(total_ha, 2)} hectares")

    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=aoi_{aoi_id}_report.pdf"},
    )
