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
from mrz_validation import detect_mrz_format, parse_mrv_a, validate_mrv_a, calculate_check_digit
from preprocessing import enhance_image_for_ocr, enhance_image_for_ocr_thresholded

import os
import re
from dataclasses import dataclass, field

import pytesseract
# Tesseract path is configured via the TESSERACT_CMD environment variable
# in main.py (set once, works on any machine/deployment) - NOT hardcoded
# here, since a hardcoded Windows path would crash on Linux deployments
# like Render.
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
    "name": re.compile(
        r"(?<!Issuing Post )(?:Name|Full Name)\s*[:\-]?\s*([A-Z][A-Za-z\s.]+?)(?=\s*\n|\s*$)",
        re.IGNORECASE,
    ),
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
    "visa_type": re.compile(
        r"Visa Type\s*(?:/\s*Class)?\s*[:\-]?\s*([A-Za-z0-9/]+(?:\s+[A-Za-z0-9/]+)?)",
        re.IGNORECASE,
    ),
    "entry_validation": re.compile(
        r"(?:Entries|Entry Validation|No\.? of Entries|Number of Entries)\s*[:\-]?\s*"
        r"(Single|Multiple|\bS\b|\bM\b|\d+)",
        re.IGNORECASE,
    ),
    "stay_duration": re.compile(
        r"(?:Duration of Stay|Length of Stay|Stay Duration|Period of Stay)\s*[:\-]?\s*(\d+\s*(?:Days?|Months?|Years?))",
        re.IGNORECASE,
    ),
    "id_number": re.compile(r"(?:ID No\.?|ID Number|License No\.?)\s*[:\-]?\s*([A-Z0-9\-]{6,15})", re.IGNORECASE),
}

# MRZ line pattern for passports (TD3 format, 2 lines of 44 chars, mostly
# uppercase letters, digits, and '<' fill characters).
MRZ_LINE_PATTERN = re.compile(r"^[A-Z0-9<]{30,44}$")


def _run_ocr(image: Image.Image) -> str:
    # eng+hin: reads both English and Hindi (Devanagari script) in the
    # same pass - needed since Indian documents (SIH26188's actual
    # scope, under SSB/border checkpoints) commonly mix both scripts on
    # one document. English-only OCR misreads Devanagari characters as
    # garbled English, and that corruption can bleed into and break
    # nearby genuine English text too.
    return pytesseract.image_to_string(image, lang="eng+hin")


def _extract_printed_fields(text: str) -> dict:
    fields = {}
    for field_name, pattern in FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            if field_name == "entry_validation":
                # Real visas often abbreviate to a single letter (US visas
                # use "M"/"S") rather than spelling out "Multiple"/"Single" -
                # normalize so the output is human-readable either way.
                if value.upper() == "M":
                    value = "Multiple (M)"
                elif value.upper() == "S":
                    value = "Single (S)"
            fields[field_name] = value
    return fields


def _find_mrz_lines(text: str) -> list[str]:
    """
    Finds two consecutive lines that may form a visa/passport MRZ.
    Handles common OCR errors in the MRZ prefix.
    """

    lines = []

    for line in text.split("\n"):
        cleaned = line.strip().replace(" ", "")

        if len(cleaned) >= 30:
            lines.append(cleaned)

    for i, line in enumerate(lines):

        # Visa MRZ prefix
        if line.startswith("V<") or line.startswith("VN"):

            if i + 1 < len(lines):
                return [line, lines[i + 1]]

        # Passport MRZ prefix
        if line.startswith("P<"):

            if i + 1 < len(lines):
                return [line, lines[i + 1]]

    return []
def _parse_mrz(mrz_lines: list[str]) -> dict:
    """
    Parses passport TD3 or visa MRV-A/MRV-B MRZ.
    """

    parsed = {}

    if len(mrz_lines) < 2:
        return parsed

    line1 = mrz_lines[0].replace(" ", "")
    line2 = mrz_lines[1].replace(" ", "")

    try:

        # Detect MRZ format
        mrz_format = detect_mrz_format(line1, line2)

        parsed["mrz_format"] = mrz_format

        # -------------------------------------------------
        # VISA MRZ
        # -------------------------------------------------

        if mrz_format == "MRV-A_VISA":

            visa_data = parse_mrv_a(line2)

            if visa_data:
                parsed["mrz_document_number"] = visa_data["document_number"]
                parsed["mrz_nationality"] = visa_data["nationality"]
                parsed["mrz_date_of_birth"] = visa_data["date_of_birth"]
                parsed["mrz_sex"] = visa_data["sex"]
                parsed["mrz_date_of_expiry"] = visa_data["valid_until"]

                # Validate MRZ checksums
                validation = validate_mrv_a(line2)
                parsed["mrz_validation"] = validation

                # Surfaced in the exact shape document_validation.py's
                # _check_mrz_checksum() reads, so the MRZ_CHECKSUM_FAILED
                # flag actually fires when a checksum genuinely fails.
                parsed["mrz_checksum_valid"] = validation["status"] == "MRZ_VALID"
                parsed["mrz_checksum_details"] = {
                    k: v for k, v in validation.items() if k != "status"
                }

            return parsed

        # -------------------------------------------------
        # PASSPORT MRZ
        # -------------------------------------------------

        if mrz_format == "PASSPORT":

            if line1.startswith("P<"):
                name_part = line1[5:].rstrip("<")
                surname, _, given_names = name_part.partition("<<")

                parsed["mrz_surname"] = surname.replace(
                    "<", " "
                ).strip()

                parsed["mrz_given_names"] = given_names.replace(
                    "<", " "
                ).strip()

            if len(line2) >= 28:
                passport_number_field = line2[0:9]
                dob_field = line2[13:19]
                expiry_field = line2[21:27]

                parsed["mrz_passport_number"] = (
                    passport_number_field.replace("<", "").strip()
                )

                parsed["mrz_nationality"] = line2[10:13].strip()

                parsed["mrz_date_of_birth"] = dob_field.strip()

                parsed["mrz_sex"] = line2[20:21].strip()

                parsed["mrz_date_of_expiry"] = expiry_field.strip()

                # Validate passport MRZ checksums (same ICAO 9303 formula
                # used for visas above) - this was previously missing for
                # passports specifically.
                if len(line2) >= 28:
                    checks = {}
                    all_valid = True

                    for check_name, (data, check_digit_char) in {
                        "passport_number": (passport_number_field, line2[9]),
                        "date_of_birth": (dob_field, line2[19]),
                        "date_of_expiry": (expiry_field, line2[27]),
                    }.items():
                        computed = calculate_check_digit(data)
                        valid = check_digit_char.isdigit() and computed == int(check_digit_char)
                        checks[check_name] = {
                            "value": data,
                            "given_check_digit": check_digit_char,
                            "calculated_check_digit": str(computed),
                            "valid": valid,
                        }
                        if not valid:
                            all_valid = False

                    # Final composite check digit (ICAO 9303 TD3, line 2,
                    # position 44): the 7-3-1 weighted sum over the
                    # CONCATENATION of the passport number, date of birth
                    # and date of expiry fields - each including its own
                    # check digit (i.e. positions 1-10, 14-20, 22-43).
                    # Deliberately only computed on a full 44-char line: on
                    # a truncated OCR line the splice points would be
                    # wrong and the result meaningless.
                    if len(line2) == 44:
                        composite_data = line2[0:10] + line2[13:20] + line2[21:43]
                        composite_given = line2[43]
                        composite_computed = calculate_check_digit(composite_data)
                        composite_valid = (
                            composite_given.isdigit()
                            and composite_computed == int(composite_given)
                        )
                        checks["composite"] = {
                            "value": composite_data,
                            "given_check_digit": composite_given,
                            "calculated_check_digit": str(composite_computed),
                            "valid": composite_valid,
                        }
                        if not composite_valid:
                            all_valid = False

                    parsed["mrz_checksum_valid"] = all_valid
                    parsed["mrz_checksum_details"] = checks

            return parsed

    except IndexError:
        pass

    return parsed

def _guess_document_type(text: str, mrz_format_detected: str | None) -> str:
    """
    Guesses which of the 5 SIH document types this is. Checks the ACTUAL
    detected MRZ format (PASSPORT vs MRV-A_VISA / MRV-B_VISA) rather than
    just whether any MRZ was found - previously, any MRZ presence
    defaulted to "passport" even when it was clearly a visa MRZ, which
    also threw off document_validation.py's field-checking downstream
    (it expects different fields for each document type). "visa" keyword
    is also checked before the generic "passport" keyword, since visa
    documents commonly mention "passport" in their own printed text.
    """
    lower = text.lower()

    if mrz_format_detected == "PASSPORT":
        return "passport"
    if mrz_format_detected in ("MRV-A_VISA", "MRV-B_VISA", "VISA_UNKNOWN_FORMAT"):
        return "visa"

    if "visa" in lower:
        return "visa"
    if "driving licence" in lower or "driving license" in lower:
        return "driving_license"
    if "permit" in lower:
        return "permit"
    if "identity card" in lower or "national id" in lower:
        return "national_id"
    if "passport" in lower:
        return "passport"
    return "unknown"


def extract_document_fields(file_path: str) -> dict:
    """
    Main entry point. Runs OCR TWICE on the document image, using two
    different preprocessing strategies, and merges the best result from
    each - this was found necessary through real testing: Otsu
    thresholding (see preprocessing.py) genuinely improves reading
    larger printed fields on watermarked/textured-background documents,
    but makes the small, dense MRZ zone WORSE, not better. Rather than
    picking one strategy and accepting a tradeoff, we run both and use
    each one where it's actually better:
      - MRZ parsing: uses the NON-thresholded (sharpened only) text,
        since thresholding was tested to introduce more corruption there.
      - Printed field extraction: tries the thresholded text first (it's
        the stronger version for this), then fills in any still-missing
        fields from the non-thresholded text as a fallback - some fields
        may extract from one version but not the other, so merging both
        catches more overall than committing to a single strategy.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    file_name = os.path.basename(file_path)
    warnings: list[str] = []
    output_dir = os.path.dirname(file_path)

    sharp_path = enhance_image_for_ocr(file_path, output_dir)
    with Image.open(sharp_path) as image:
        raw_text_sharp = _run_ocr(image)

    thresh_path = enhance_image_for_ocr_thresholded(file_path, output_dir)
    with Image.open(thresh_path) as image:
        raw_text_thresh = _run_ocr(image)

    if not raw_text_sharp.strip() and not raw_text_thresh.strip():
        warnings.append(
            "No text could be extracted from this image. Check image quality, "
            "orientation, and lighting."
        )

    # MRZ: use the non-thresholded text - tested to be more reliable for
    # this specific small, dense monospace zone. Fall back to the
    # thresholded text only if the sharpened version found nothing.
    mrz_lines = _find_mrz_lines(raw_text_sharp)
    mrz_fields = _parse_mrz(mrz_lines)
    if not mrz_fields:
        mrz_lines_fallback = _find_mrz_lines(raw_text_thresh)
        mrz_fields = _parse_mrz(mrz_lines_fallback)
        if mrz_fields:
            mrz_lines = mrz_lines_fallback

    if mrz_lines and not mrz_fields:
        warnings.append(
            "Detected what looks like an MRZ zone but could not reliably parse it - "
            "OCR quality on this region may be too low."
        )

    # Printed fields: merge results from both versions - thresholded
    # text takes priority (tested as the stronger version for printed
    # fields), non-thresholded text fills in anything still missing.
    printed_fields_thresh = _extract_printed_fields(raw_text_thresh)
    printed_fields_sharp = _extract_printed_fields(raw_text_sharp)
    printed_fields = {**printed_fields_sharp, **printed_fields_thresh}

    all_fields = {**printed_fields, **mrz_fields}
    # Use whichever raw text is longer/richer for document-type keyword
    # guessing and as the canonical raw_text shown in the API response.
    raw_text = raw_text_thresh if len(raw_text_thresh) >= len(raw_text_sharp) else raw_text_sharp
    doc_type = _guess_document_type(raw_text_sharp + " " + raw_text_thresh, mrz_fields.get("mrz_format"))

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
