"""
Module 1: OCR Extraction
SIH26188 - AI-Based Fake Identity & Document Screening System

Automatically extracts structured identity fields (name, passport number,
nationality, dates, etc.) from passport, visa, national ID, driving
license, or permit document images.

--- Approach ---
Uses Tesseract OCR (same engine as text_manipulation.py) to read all text
from the document, then applies regex/pattern-based field extraction to
pull out specific labeled fields. This is a rule-based extraction
approach - reliable and explainable for a hackathon prototype, though a
production system might use a fine-tuned document-specific OCR model
(e.g. specialized passport MRZ readers) for higher accuracy.

Special handling for passports: the Machine Readable Zone (MRZ) - the two
lines of `<<<` formatted text at the bottom of every passport photo page -
is parsed separately, since it's a standardized format (ICAO 9303) and is
far more reliable to extract than the printed fields above it.

Usage:
    from ocr_extraction import extract_document_fields

    result = extract_document_fields("path/to/passport.jpg")
    print(result["extracted_fields"])
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pytesseract
from PIL import Image


@dataclass
class ExtractionResult:
    file_name: str
    document_type_guess: str = "unknown"
    extracted_fields: dict = field(default_factory=dict)
    raw_text: str = ""
    mrz_detected: bool = False
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "document_type_guess": self.document_type_guess,
            "extracted_fields": self.extracted_fields,
            "mrz_detected": self.mrz_detected,
            "warnings": self.warnings,
            "raw_text": self.raw_text,
        }


# --- Field patterns for standard printed fields ---
FIELD_PATTERNS = {
    "name": re.compile(r"(?:Name|Full Name)\s*[:\-]?\s*([A-Z][A-Za-z\s.]+?)(?=\s*\n|\s*$)", re.IGNORECASE),
    "date_of_birth": re.compile(
        r"(?:Date of Birth|DOB|Birth)\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
        re.IGNORECASE,
    ),
    "date_of_expiry": re.compile(
        r"(?:Date of Expiry|Expiry|Valid Till|Valid Until)\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
        re.IGNORECASE,
    ),
    "passport_number": re.compile(r"(?:Passport No\.?|Passport Number)\s*[:\-]?\s*([A-Z0-9]{6,9})", re.IGNORECASE),
    "nationality": re.compile(r"Nationality\s*[:\-]?\s*([A-Za-z\s]+?)(?=\s*\n|\s*$)", re.IGNORECASE),
    "gender": re.compile(r"(?:Sex|Gender)\s*[:\-]?\s*(M|F|Male|Female)", re.IGNORECASE),
    "visa_number": re.compile(r"Visa\s*(?:No\.?|Number)\s*[:\-]?\s*([A-Z0-9]{6,12})", re.IGNORECASE),
    "visa_type": re.compile(r"Visa Type\s*[:\-]?\s*([A-Za-z0-9\-]+)", re.IGNORECASE),
    "id_number": re.compile(r"(?:ID No\.?|ID Number|License No\.?)\s*[:\-]?\s*([A-Z0-9\-]{6,15})", re.IGNORECASE),
}

# MRZ line pattern for passports (TD3 format, 2 lines of 44 chars, mostly
# uppercase letters, digits, and '<' fill characters).
MRZ_LINE_PATTERN = re.compile(r"^[A-Z0-9<]{30,44}$")


def _run_ocr(image: Image.Image) -> str:
    return pytesseract.image_to_string(image)


def _extract_printed_fields(text: str) -> dict:
    fields = {}
    for field_name, pattern in FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            fields[field_name] = match.group(1).strip()
    return fields


def _find_mrz_lines(text: str) -> list[str]:
    """
    Looks for lines that resemble MRZ format (long uppercase strings with
    '<' padding characters) among the OCR'd text lines.
    """
    candidate_lines = []
    for line in text.split("\n"):
        cleaned = line.strip().replace(" ", "")
        if len(cleaned) >= 30 and "<" in cleaned:
            candidate_lines.append(cleaned)
    return candidate_lines


def _parse_mrz(mrz_lines: list[str]) -> dict:
    """
    Parses a standard TD3 (passport) MRZ if 2 valid-looking lines are
    found. This format is standardized (ICAO 9303), so field positions
    are fixed:
      Line 1: P<COUNTRY<SURNAME<<GIVEN<NAMES<<<<<<<<<<<<<<<<<<<<<<<
      Line 2: PASSPORTNO<CHECK COUNTRY BIRTHDATE<CHECK SEX EXPIRY<CHECK...
    OCR quality on MRZ text is often imperfect, so this is best-effort
    parsing, not guaranteed - flagged as such in warnings if fields look
    malformed.
    """
    parsed = {}
    if len(mrz_lines) < 2:
        return parsed

    line1, line2 = mrz_lines[0], mrz_lines[1]

    try:
        if line1.startswith("P<"):
            name_part = line1[5:].rstrip("<")
            surname, _, given_names = name_part.partition("<<")
            parsed["mrz_surname"] = surname.replace("<", " ").strip()
            parsed["mrz_given_names"] = given_names.replace("<", " ").strip()

        if len(line2) >= 28:
            parsed["mrz_passport_number"] = line2[0:9].replace("<", "").strip()
            parsed["mrz_nationality"] = line2[10:13].strip()
            parsed["mrz_date_of_birth"] = line2[13:19].strip()  # YYMMDD
            parsed["mrz_sex"] = line2[20:21].strip()
            parsed["mrz_date_of_expiry"] = line2[21:27].strip()  # YYMMDD
    except IndexError:
        pass  # malformed/incomplete MRZ - just return what we got

    return parsed


def _guess_document_type(text: str, mrz_found: bool) -> str:
    lower = text.lower()
    if mrz_found or "passport" in lower:
        return "passport"
    if "visa" in lower:
        return "visa"
    if "driving licence" in lower or "driving license" in lower:
        return "driving_license"
    if "permit" in lower:
        return "permit"
    if "identity card" in lower or "national id" in lower:
        return "national_id"
    return "unknown"


def extract_document_fields(file_path: str) -> dict:
    """
    Main entry point. Runs OCR on the document image and extracts
    structured identity fields, using both printed-field pattern matching
    and MRZ parsing (for passports) where applicable.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    file_name = os.path.basename(file_path)
    warnings: list[str] = []

    with Image.open(file_path) as image:
        raw_text = _run_ocr(image)

    if not raw_text.strip():
        warnings.append(
            "No text could be extracted from this image. Check image quality, "
            "orientation, and lighting."
        )

    printed_fields = _extract_printed_fields(raw_text)
    mrz_lines = _find_mrz_lines(raw_text)
    mrz_fields = _parse_mrz(mrz_lines)

    if mrz_lines and not mrz_fields:
        warnings.append(
            "Detected what looks like an MRZ zone but could not reliably parse it - "
            "OCR quality on this region may be too low."
        )

    all_fields = {**printed_fields, **mrz_fields}
    doc_type = _guess_document_type(raw_text, bool(mrz_fields))

    if not all_fields:
        warnings.append(
            "No structured fields could be confidently extracted. The document may "
            "use an unrecognized layout, or image quality may be insufficient."
        )

    result = ExtractionResult(
        file_name=file_name,
        document_type_guess=doc_type,
        extracted_fields=all_fields,
        raw_text=raw_text.strip(),
        mrz_detected=bool(mrz_fields),
        warnings=warnings,
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python ocr_extraction.py <path_to_document_image>")
        sys.exit(1)

    report = extract_document_fields(sys.argv[1])
    print(json.dumps(report, indent=2, default=str))
