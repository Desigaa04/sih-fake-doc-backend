"""
Text Manipulation Detection Module
SIH26188 - AI-Based Fake Identity & Document Screening System

Detects signs that text fields on a document (name, DOB, ID number, etc.)
may have been digitally altered.

--- Approach (kept deliberately simple for a hackathon prototype) ---
Full "was this exact character edited" detection needs deep font-forensics
and is a hard research problem on its own. For a prototype, we focus on
signals that are genuinely achievable and still meaningful:

1. OCR extraction - read all text on the document using Tesseract OCR.
2. Field format validation - check if key fields (dates, ID numbers) match
   the expected pattern for that document type. Edited fields often break
   formatting (e.g. a tampered DOB like "31/13/2005" - invalid month).
3. Font/spacing consistency - genuine documents are printed with uniform
   font size and consistent character spacing across a line. When a field
   is edited digitally (even carefully), it's common for the replacement
   text's height/spacing to differ subtly from the surrounding printed
   text. We detect this using bounding-box statistics from OCR output.
4. Alignment consistency - characters in a genuinely printed field usually
   sit on a consistent baseline (same vertical position). Pasted/edited
   text often sits slightly off the original baseline.

None of this proves forgery by itself - it's explainable, rule-based
evidence to feed into the overall risk score, same philosophy as the other
modules. A human reviewer makes the final call.

Usage:
    from text_manipulation import analyze_text_manipulation

    result = analyze_text_manipulation("path/to/document.jpg")
    print(result["risk_score"], result["flags"])
    print(result["extracted_text"])
"""

from __future__ import annotations

import os
import re
import statistics
from dataclasses import dataclass, field

import pytesseract
from pytesseract import Output
from PIL import Image

# Character height / spacing variance thresholds - tuned loosely; a real
# deployment would calibrate these against the specific document type's
# known-genuine samples.
FONT_HEIGHT_CV_THRESHOLD = 0.35  # coefficient of variation (std/mean)
BASELINE_VARIANCE_THRESHOLD = 6  # pixels

# Common ID-field patterns to sanity-check (extend this per document type
# you're targeting, e.g. Aadhaar, PAN, driving license, student ID)
DATE_PATTERN = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
ID_NUMBER_PATTERN = re.compile(r"\b[A-Z0-9]{6,}\b")


@dataclass
class TextFlag:
    code: str
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class TextManipulationResult:
    file_name: str
    extracted_text: str = ""
    flags: list[TextFlag] = field(default_factory=list)
    risk_score: int = 0

    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "risk_score": self.risk_score,
            "extracted_text": self.extracted_text,
            "flags": [
                {"code": f.code, "description": f.description, "severity": f.severity}
                for f in self.flags
            ],
        }


SEVERITY_WEIGHTS = {"low": 10, "medium": 25, "high": 40}


def _run_ocr(image: Image.Image) -> dict:
    """
    Runs Tesseract OCR and returns detailed output including per-word
    bounding boxes (needed for the font/spacing/baseline checks), not just
    plain text.
    """
    # eng+hin: same reasoning as ocr_extraction.py's _run_ocr() - Indian
    # documents commonly mix Hindi (Devanagari) and English, and
    # English-only OCR here would produce garbled word boxes, causing
    # false INCONSISTENT_FONT_SIZE / BASELINE_MISALIGNMENT flags on
    # genuinely normal bilingual documents.
    return pytesseract.image_to_data(image, lang="eng+hin", output_type=Output.DICT)


def _extract_plain_text(ocr_data: dict) -> str:
    words = [w.strip() for w in ocr_data.get("text", []) if w.strip()]
    return " ".join(words)


def _check_date_validity(text: str, flags: list[TextFlag]) -> None:
    """
    Finds date-like patterns in the extracted text and checks whether they
    are calendar-valid (e.g. flags month=13 or day=32). A tampered date
    field sometimes ends up invalid if a digit was swapped carelessly.
    """
    for match in DATE_PATTERN.finditer(text):
        day, month, year = match.groups()
        try:
            day_i, month_i = int(day), int(month)
            if not (1 <= month_i <= 12) or not (1 <= day_i <= 31):
                flags.append(TextFlag(
                    code="INVALID_DATE_FORMAT",
                    description=f"Found a date-like value '{match.group(0)}' that is not a "
                                f"valid calendar date. This can indicate a digit was altered "
                                f"in a date field.",
                    severity="medium",
                ))
        except ValueError:
            continue


def _check_font_height_consistency(ocr_data: dict, flags: list[TextFlag]) -> None:
    """
    Genuine printed lines use a consistent font size WITHIN that line -
    but different lines/fields on a document (e.g. a big title vs
    smaller body text vs tiny MRZ text) naturally differ in size by
    design, which is normal and should NOT be flagged. This checks each
    line separately (same grouping as _check_baseline_consistency
    above), rather than computing one variation score across the whole
    document, which previously mixed titles/labels/data together and
    fired on nearly every real document layout.
    """
    lines: dict[tuple, list[int]] = {}
    n = len(ocr_data.get("text", []))
    for i in range(n):
        txt = ocr_data["text"][i].strip()
        h = ocr_data["height"][i]
        if not txt or h <= 0:
            continue
        key = (ocr_data["block_num"][i], ocr_data["par_num"][i], ocr_data["line_num"][i])
        lines.setdefault(key, []).append(h)

    offending_lines = 0
    lines_checked = 0
    for key, heights in lines.items():
        if len(heights) < 3:
            continue  # need a few words on the SAME line to judge consistency
        lines_checked += 1
        mean_h = statistics.mean(heights)
        std_h = statistics.stdev(heights)
        cv = std_h / mean_h if mean_h > 0 else 0
        if cv > FONT_HEIGHT_CV_THRESHOLD:
            offending_lines += 1

    if lines_checked > 0 and offending_lines > 0:
        flags.append(TextFlag(
            code="INCONSISTENT_FONT_SIZE",
            description=f"Found {offending_lines} line(s) (out of {lines_checked} checked) "
                        f"where words on the SAME line have inconsistent heights. Genuine "
                        f"printed lines keep a consistent font size within that line; this can "
                        f"indicate a word was pasted in from a different source. (Normal "
                        f"document-wide differences, like a large title vs smaller body text, "
                        f"are not flagged.)",
            severity="medium",
        ))


def _check_baseline_consistency(ocr_data: dict, flags: list[TextFlag]) -> None:
    """
    Groups words by their OCR-detected line number and checks whether
    words on the same line sit on a consistent vertical baseline (top +
    height should align closely). A word sitting noticeably above/below
    its line's baseline can indicate it was pasted in separately and not
    perfectly aligned with the original text.
    """
    lines: dict[tuple, list[int]] = {}
    n = len(ocr_data.get("text", []))
    for i in range(n):
        txt = ocr_data["text"][i].strip()
        if not txt:
            continue
        key = (ocr_data["block_num"][i], ocr_data["par_num"][i], ocr_data["line_num"][i])
        baseline_y = ocr_data["top"][i] + ocr_data["height"][i]
        lines.setdefault(key, []).append(baseline_y)

    offending_lines = 0
    for key, baselines in lines.items():
        if len(baselines) < 3:
            continue  # need a few words on a line to judge alignment
        spread = max(baselines) - min(baselines)
        if spread > BASELINE_VARIANCE_THRESHOLD:
            offending_lines += 1

    if offending_lines > 0:
        flags.append(TextFlag(
            code="BASELINE_MISALIGNMENT",
            description=f"Found {offending_lines} line(s) of text where words are not sitting "
                        f"on a consistent baseline. This can indicate a word or field was "
                        f"pasted in and not perfectly aligned with the original printed text.",
            severity="low" if offending_lines == 1 else "medium",
        ))


def _check_ocr_confidence(ocr_data: dict, flags: list[TextFlag]) -> None:
    """
    Tesseract provides a confidence score per detected word. Isolated
    words with very low confidence surrounded by high-confidence text can
    indicate that region was altered/is of different visual quality than
    the rest of the (presumably genuine) printed document.
    """
    confidences = [
        int(c) for c, txt in zip(ocr_data.get("conf", []), ocr_data.get("text", []))
        if txt.strip() and str(c).lstrip("-").isdigit()
    ]
    confidences = [c for c in confidences if c >= 0]  # -1 means no text detected

    if len(confidences) < 4:
        return

    mean_conf = statistics.mean(confidences)
    low_conf_words = [c for c in confidences if c < mean_conf - 30 and c < 50]

    if low_conf_words:
        flags.append(TextFlag(
            code="LOW_CONFIDENCE_TEXT_REGION",
            description=f"Found {len(low_conf_words)} word(s) with unusually low OCR "
                        f"confidence relative to the rest of the document's text. This can "
                        f"indicate that region has different visual characteristics (e.g. "
                        f"from being edited/pasted) than genuinely printed text.",
            severity="low",
        ))


def analyze_text_manipulation(file_path: str) -> dict:
    """
    Main entry point. Runs OCR + consistency checks on the document image
    and returns a risk report with flags.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    file_name = os.path.basename(file_path)
    flags: list[TextFlag] = []

    with Image.open(file_path) as image:
        ocr_data = _run_ocr(image)

    extracted_text = _extract_plain_text(ocr_data)

    if not extracted_text:
        flags.append(TextFlag(
            code="NO_TEXT_DETECTED",
            description="No readable text was detected on the document. This may mean the "
                        "image quality is too low, or the document is oriented/cropped "
                        "incorrectly - not necessarily a sign of forgery.",
            severity="low",
        ))
    else:
        _check_date_validity(extracted_text, flags)
        _check_font_height_consistency(ocr_data, flags)
        _check_baseline_consistency(ocr_data, flags)
        _check_ocr_confidence(ocr_data, flags)

    risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))

    result = TextManipulationResult(
        file_name=file_name,
        extracted_text=extracted_text,
        flags=flags,
        risk_score=risk_score,
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python text_manipulation.py <path_to_image>")
        sys.exit(1)

    report = analyze_text_manipulation(sys.argv[1])
    print(json.dumps(report, indent=2, default=str))
