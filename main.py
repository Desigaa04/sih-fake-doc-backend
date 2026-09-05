"""
Main API - AI-Based Fake Identity & Document Screening System
SIH26188

This is the backend entry point. It exposes one main endpoint,
POST /screen-document, which:

1. Accepts a document image (required), and optionally a selfie (for face
   verification) and a stamp crop image (for stamp forgery detection).
2. Runs the document through all 6 detection modules.
3. Combines every module's result into one final, explainable verdict
   using aggregator.py.

Run this locally with:
    uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs in your browser - FastAPI
auto-generates an interactive test page there, where you can upload
files and see results without needing the frontend at all. This is
great for testing today, and also great to show judges directly if the
frontend isn't ready in time.
"""

import os
import shutil
import tempfile

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

import pytesseract

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

from ocr_extraction import extract_document_fields
from document_validation import validate_document_fields
from text_manipulation import analyze_text_manipulation
from photo_replacement import analyze_photo_replacement
from face_verification import analyze_face_verification
from stamp_forgery import analyze_stamp_forgery
from metadata_analysis import analyze_metadata
from aggregator import aggregate_results

app = FastAPI(title="AI-Based Fake Identity Document Screening System")

# Allows your frontend (running on a different port, e.g. React on :3000)
# to call this API without being blocked by the browser. Fine to leave
# wide open ("*") for a hackathon demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folder where sample genuine stamp images should be placed for the
# stamp_forgery module to compare against. Create this folder and drop in
# 3-5 sample stamp crop images before your demo.
REFERENCE_STAMPS_DIR = "reference_stamps"


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Fake Document Screening API is running"}


@app.post("/screen-document")
async def screen_document(
    document: UploadFile = File(...),
    selfie: Optional[UploadFile] = File(None),
    stamp_crop: Optional[UploadFile] = File(None),
):
    """
    Main screening endpoint.

    - document: the ID/passport/document image to check (required)
    - selfie: a live photo of the person, for face verification (optional)
    - stamp_crop: a cropped image of just the stamp/seal region, for stamp
      forgery detection (optional)

    Returns the combined, explainable verdict from aggregator.py.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_path = os.path.join(tmp_dir, document.filename)
        with open(doc_path, "wb") as f:
            shutil.copyfileobj(document.file, f)

        module_results = {}

        # Module 1 + 2: extract fields, then validate them
        extraction = extract_document_fields(doc_path)
        module_results["ocr_extraction"] = extraction

        validation = validate_document_fields(
            extraction["extracted_fields"], extraction["document_type_guess"]
        )
        module_results["document_validation"] = validation

        # Independent checks - always run on the main document image
        module_results["text_manipulation"] = analyze_text_manipulation(doc_path)
        module_results["photo_replacement"] = analyze_photo_replacement(
            doc_path, save_ela_visual=False
        )
        module_results["metadata_analysis"] = analyze_metadata(doc_path)

        # Optional: face verification, only if a selfie was uploaded
        if selfie is not None:
            selfie_path = os.path.join(tmp_dir, selfie.filename)
            with open(selfie_path, "wb") as f:
                shutil.copyfileobj(selfie.file, f)
            module_results["face_verification"] = analyze_face_verification(
                doc_path, selfie_path
            )

        # Optional: stamp forgery check, only if a stamp crop was uploaded
        if stamp_crop is not None:
            stamp_path = os.path.join(tmp_dir, stamp_crop.filename)
            with open(stamp_path, "wb") as f:
                shutil.copyfileobj(stamp_crop.file, f)
            module_results["stamp_forgery"] = analyze_stamp_forgery(
                stamp_path, REFERENCE_STAMPS_DIR
            )

        final_report = aggregate_results(module_results)

    return final_report
