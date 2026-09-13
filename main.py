"""
Main API - AI-Based Fake Identity & Document Screening System
SIH26188 - Ministry of Home Affairs, Sashastra Seema Bal (SSB)

Endpoints:
    GET  /                      - the web UI (upload page + dashboard)
    GET  /health                - health check
    POST /screen-document       - screen a single document
    POST /screen-batch          - screen multiple documents at once
    GET  /audit-trail           - recent screening history (in-memory)
    GET  /generate-report/{id}  - download a PDF report for a past result

Run this locally with:
    uvicorn main:app --reload

Then open http://127.0.0.1:8000 in your browser.
"""

import base64
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from typing import Optional

import pytesseract
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

# --- Tesseract OCR setup ---
# pytesseract needs the actual Tesseract OCR program installed on your
# computer (separate from the pip package, which is just a Python
# wrapper). If Tesseract isn't on your system PATH, set the TESSERACT_CMD
# environment variable to its install location instead of editing code,
# e.g. on Windows:
#   setx TESSERACT_CMD "C:\Program Files\Tesseract-OCR\tesseract.exe"
tesseract_cmd = os.environ.get("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

from aggregator import aggregate_results
from document_validation import validate_document_fields
from face_verification import analyze_face_verification
from metadata_analysis import analyze_metadata
from ocr_extraction import extract_document_fields
from photo_replacement import analyze_photo_replacement
from report_generator import build_pdf_report
from stamp_forgery import analyze_stamp_forgery
from text_manipulation import analyze_text_manipulation
from frontend import UPLOAD_PAGE_HTML

app = FastAPI(title="AI-Based Fake Identity Document Screening System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folder where sample genuine stamp images should be placed for the
# stamp_forgery module to compare against.
REFERENCE_STAMPS_DIR = "reference_stamps"

# --- In-memory stores (reset on server restart - fine for a hackathon
# demo; a production deployment would use a real database here, which
# directly supports the PS's stated goal of a "digital trail for
# investigations") ---
AUDIT_LOG: list[dict] = []
REPORTS: dict[str, dict] = {}
MAX_AUDIT_ENTRIES = 200
MAX_STORED_REPORTS = 200


def _run_pipeline(doc_path: str, tmp_dir: str, selfie_path: Optional[str] = None,
                   stamp_path: Optional[str] = None) -> tuple[dict, Optional[str]]:
    """
    Runs the full 7-module screening pipeline on one document and returns
    (final_report, ela_heatmap_base64). Shared by both the single-document
    and batch endpoints so the logic only lives in one place.
    """
    module_results = {}

    extraction = extract_document_fields(doc_path)
    module_results["ocr_extraction"] = extraction

    validation = validate_document_fields(
        extraction["extracted_fields"], extraction["document_type_guess"]
    )
    module_results["document_validation"] = validation

    module_results["text_manipulation"] = analyze_text_manipulation(doc_path)

    # save_ela_visual=True so we can show the heatmap in the UI - this is
    # what actually lets a reviewer SEE where tampering was detected,
    # rather than just reading a number.
    photo_result = analyze_photo_replacement(doc_path, save_ela_visual=True)
    module_results["photo_replacement"] = photo_result

    ela_b64 = None
    ela_path = photo_result.get("ela_image_path")
    if ela_path and os.path.exists(ela_path):
        with open(ela_path, "rb") as f:
            ela_b64 = base64.b64encode(f.read()).decode("ascii")

    module_results["metadata_analysis"] = analyze_metadata(doc_path)

    if selfie_path is not None:
        module_results["face_verification"] = analyze_face_verification(doc_path, selfie_path)

    if stamp_path is not None:
        module_results["stamp_forgery"] = analyze_stamp_forgery(stamp_path, REFERENCE_STAMPS_DIR)

    final_report = aggregate_results(module_results)
    return final_report, ela_b64


def _save_upload(upload: UploadFile, tmp_dir: str) -> str:
    path = os.path.join(tmp_dir, upload.filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path


def _log_and_store(final_report: dict, filename: str, ela_b64: Optional[str]) -> str:
    """Records this screening in the in-memory audit trail and report
    store, and returns a unique report_id used to fetch a PDF later."""
    report_id = uuid.uuid4().hex[:10].upper()
    timestamp = datetime.now().isoformat(timespec="seconds")

    AUDIT_LOG.append({
        "report_id": report_id,
        "timestamp": timestamp,
        "filename": filename,
        "verdict": final_report["verdict"],
        "risk_score": final_report["final_risk_score"],
        "trust_score": final_report["final_trust_score"],
    })
    if len(AUDIT_LOG) > MAX_AUDIT_ENTRIES:
        del AUDIT_LOG[0]

    REPORTS[report_id] = {
        "report": final_report,
        "filename": filename,
        "timestamp": timestamp,
    }
    if len(REPORTS) > MAX_STORED_REPORTS:
        oldest_key = next(iter(REPORTS))
        del REPORTS[oldest_key]

    final_report["report_id"] = report_id
    final_report["ela_heatmap_base64"] = ela_b64
    return report_id


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Fake Document Screening API is running"}


@app.get("/", response_class=HTMLResponse)
def upload_page():
    return UPLOAD_PAGE_HTML


@app.post("/screen-document")
async def screen_document(
    document: UploadFile = File(...),
    selfie: Optional[UploadFile] = File(None),
    stamp_crop: Optional[UploadFile] = File(None),
):
    """
    Screens a single document through all 7 modules and returns the
    combined, explainable verdict - including a base64 ELA heatmap image
    (for visualizing detected tampering) and a report_id you can use with
    GET /generate-report/{report_id} to download a PDF summary.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_path = _save_upload(document, tmp_dir)
        selfie_path = _save_upload(selfie, tmp_dir) if selfie is not None else None
        stamp_path = _save_upload(stamp_crop, tmp_dir) if stamp_crop is not None else None

        final_report, ela_b64 = _run_pipeline(doc_path, tmp_dir, selfie_path, stamp_path)
        _log_and_store(final_report, document.filename, ela_b64)

    return final_report


@app.post("/screen-batch")
async def screen_batch(documents: list[UploadFile] = File(...)):
    """
    Screens multiple documents in one request - simulates a checkpoint
    processing a queue of travelers/applicants. Returns a summary count
    (how many genuine / needs review / likely fake) plus each individual
    result, and logs every one to the audit trail.
    """
    if not documents:
        raise HTTPException(status_code=400, detail="No documents provided.")

    results = []
    summary = {"Likely Genuine": 0, "Needs Manual Review": 0, "Likely Fake": 0}

    for upload in documents:
        with tempfile.TemporaryDirectory() as tmp_dir:
            doc_path = _save_upload(upload, tmp_dir)
            final_report, ela_b64 = _run_pipeline(doc_path, tmp_dir)
            _log_and_store(final_report, upload.filename, ela_b64)

        summary[final_report["verdict"]] = summary.get(final_report["verdict"], 0) + 1
        results.append({
            "filename": upload.filename,
            "report_id": final_report["report_id"],
            "verdict": final_report["verdict"],
            "risk_score": final_report["final_risk_score"],
            "trust_score": final_report["final_trust_score"],
            "top_reasons": final_report["top_reasons"],
        })

    return {"summary": summary, "total": len(documents), "results": results}


@app.get("/audit-trail")
def get_audit_trail(limit: int = 50):
    """
    Returns the most recent screening events, newest first - this is the
    "digital trail for investigations and intelligence analysis" the
    problem statement explicitly asks for. In-memory only for this
    prototype; a production deployment would persist this to a database.
    """
    recent = list(reversed(AUDIT_LOG))[:limit]
    return {"count": len(AUDIT_LOG), "entries": recent}


@app.get("/generate-report/{report_id}")
def generate_report(report_id: str):
    """Generates and returns a downloadable PDF summary of a past screening."""
    stored = REPORTS.get(report_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Report not found. It may have expired from memory.")

    pdf_bytes = build_pdf_report(stored["report"], filename=stored["filename"], report_id=report_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="screening_report_{report_id}.pdf"'},
    )
