"""
Module 2: Document Validation
SIH26188 - AI-Based Fake Identity & Document Screening System

Takes the structured fields extracted by Module 1 (ocr_extraction.py) and
validates them against expected formats, standards, and logical rules -
e.g. is the date of expiry actually in the future, does the passport
number match the correct format for its country, is the date of birth a
plausible age.

This is deliberately rule-based (not AI/ML) - validation rules should be
transparent and auditable, which is how real document-checking systems
work (e.g. passport control checks against known formats, not a black-box
model). This module works together with ocr_extraction.py's output:

    from ocr_extraction import extract_document_fields
    from document_validation import validate_document_fields

    extraction = extract_document_fields("passport.jpg")
    validation = validate_document_fields(extraction["extracted_fields"],
                                            extraction["document_type_guess"])

Usage (standalone):
    python document_validation.py <path_to_document_image>
    (this internally calls ocr_extraction.py first, then validates)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class ValidationFlag:
    code: str
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class ValidationResult:
    document_type: str
    fields_validated: int = 0
    flags: list = field(default_factory=list)
    risk_score: int = 0

    def to_dict(self) -> dict:
        return {
            "document_type": self.document_type,
            "fields_validated": self.fields_validated,
            "risk_score": self.risk_score,
            "flags": [
                {"code": f.code, "description": f.description, "severity": f.severity}
                for f in self.flags
            ],
        }


SEVERITY_WEIGHTS = {"low": 10, "medium": 25, "high": 40}

# Reasonable human age bounds for plausibility checking
MIN_PLAUSIBLE_AGE = 0
MAX_PLAUSIBLE_AGE = 120

# Common passport number format: 1 letter + 7 digits (India format used
# as the default example; extend/adjust per country if needed)
PASSPORT_NUMBER_PATTERN = re.compile(r"^[A-Z]\d{7}$")

DATE_FORMATS_TO_TRY = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]
# Note: "%Y%m%d" was deliberately removed - Python's strptime matches it
# against unseparated digit strings of ANY length (including 6-digit MRZ
# dates) using ambiguous greedy digit-grouping, which silently produces
# wrong dates (e.g. "000815" was misparsed as year=8, not year=2000).
# The dedicated MRZ YYMMDD handling below is the correct path for
# unseparated 6-digit dates.


def _resolve_two_digit_year(yy: int, bias: str) -> int:
    """
    Resolves a 2-digit MRZ year to a full 4-digit year. MRZ dates don't
    encode century, so we have to infer it - and birth dates vs expiry
    dates need OPPOSITE assumptions:
      - Birth dates should resolve to the most recent year that is not
        in the future (people aren't born in the future).
      - Expiry dates should resolve to a year at or after the current
        year (a passport that "expired 94 years ago" almost always
        actually means 20xx, not 19xx).
    """
    current_year = datetime.now().year
    current_century_base = (current_year // 100) * 100
    candidate_current = current_century_base + yy
    candidate_prev = candidate_current - 100
    candidate_next = candidate_current + 100

    if bias == "past":
        candidates = [c for c in (candidate_current, candidate_prev) if c <= current_year]
        return max(candidates) if candidates else candidate_prev
    else:  # bias == "future"
        # Prefer the current-century candidate unless it's implausibly
        # far in the past for an expiry date.
        if candidate_current >= current_year - 1:
            return candidate_current
        return candidate_next


def _try_parse_date(date_str: str, mrz_year_bias: str = "past") -> date | None:
    """
    Attempts to parse a date string using several common formats.

    mrz_year_bias only affects raw 6-digit MRZ-style dates (YYMMDD),
    which don't carry century information - pass "past" for birth dates
    and "future" for expiry dates so the 2-digit year resolves sensibly.
    """
    date_str = date_str.strip()

    for fmt in DATE_FORMATS_TO_TRY:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    # Handle MRZ-style YYMMDD (6 digits, no separators) - needs century
    # inference since MRZ only stores 2-digit years
    if re.match(r"^\d{6}$", date_str):
        yy, mm, dd = int(date_str[0:2]), int(date_str[2:4]), int(date_str[4:6])
        year = _resolve_two_digit_year(yy, bias=mrz_year_bias)
        try:
            return date(year, mm, dd)
        except ValueError:
            return None

    return None


def _check_expiry_date(fields: dict, flags: list[ValidationFlag]) -> None:
    expiry_str = fields.get("date_of_expiry") or fields.get("mrz_date_of_expiry")
    if not expiry_str:
        return

    expiry_date = _try_parse_date(expiry_str, mrz_year_bias="future")
    if expiry_date is None:
        flags.append(ValidationFlag(
            code="UNPARSEABLE_EXPIRY_DATE",
            description=f"Could not parse the expiry date value '{expiry_str}' into a "
                        f"valid calendar date.",
            severity="medium",
        ))
        return

    today = date.today()
    if expiry_date < today:
        flags.append(ValidationFlag(
            code="DOCUMENT_EXPIRED",
            description=f"This document's expiry date ({expiry_date.isoformat()}) has "
                        f"already passed. The document is no longer valid.",
            severity="high",
        ))
    elif (expiry_date - today).days > 365 * 15:
        # Most ID documents aren't valid for more than ~10-15 years
        flags.append(ValidationFlag(
            code="UNUSUALLY_LONG_VALIDITY",
            description=f"This document's expiry date ({expiry_date.isoformat()}) is "
                        f"unusually far in the future for a standard identity document, "
                        f"which can indicate a tampered or fabricated date field.",
            severity="medium",
        ))


def _check_date_of_birth(fields: dict, flags: list[ValidationFlag]) -> None:
    dob_str = fields.get("date_of_birth") or fields.get("mrz_date_of_birth")
    if not dob_str:
        return

    dob = _try_parse_date(dob_str)
    if dob is None:
        flags.append(ValidationFlag(
            code="UNPARSEABLE_DOB",
            description=f"Could not parse the date of birth value '{dob_str}' into a "
                        f"valid calendar date.",
            severity="medium",
        ))
        return

    today = date.today()
    if dob > today:
        flags.append(ValidationFlag(
            code="FUTURE_DATE_OF_BIRTH",
            description=f"The date of birth ({dob.isoformat()}) is in the future, which "
                        f"is not possible - this strongly suggests a tampered or "
                        f"incorrectly entered date field.",
            severity="high",
        ))
        return

    age = (today - dob).days / 365.25
    if age > MAX_PLAUSIBLE_AGE:
        flags.append(ValidationFlag(
            code="IMPLAUSIBLE_AGE",
            description=f"The calculated age ({age:.0f} years) based on this date of "
                        f"birth is implausible for a living document holder.",
            severity="medium",
        ))


def _check_passport_number_format(fields: dict, doc_type: str, flags: list[ValidationFlag]) -> None:
    if doc_type != "passport":
        return

    passport_no = fields.get("passport_number") or fields.get("mrz_passport_number")
    if not passport_no:
        return

    if not PASSPORT_NUMBER_PATTERN.match(passport_no.strip().upper()):
        flags.append(ValidationFlag(
            code="INVALID_PASSPORT_NUMBER_FORMAT",
            description=f"The passport number '{passport_no}' does not match the "
                        f"expected format (1 letter followed by 7 digits, e.g. M1234567). "
                        f"This may indicate a typo, an unsupported passport format, or a "
                        f"tampered field - worth reviewing.",
            severity="medium",
        ))


def _check_field_consistency(fields: dict, flags: list[ValidationFlag]) -> None:
    """
    Cross-checks fields that appear from BOTH printed-text extraction and
    MRZ parsing (when both are available on a passport) - a mismatch
    between the two is a strong tampering signal, since forging both the
    printed text AND the MRZ consistently is much harder to pull off.
    """
    # Text fields: compared as cleaned strings (letters/digits only)
    text_checks = [
        ("passport_number", "mrz_passport_number", "passport number"),
    ]

    for printed_key, mrz_key, label in text_checks:
        printed_val = fields.get(printed_key)
        mrz_val = fields.get(mrz_key)
        if not printed_val or not mrz_val:
            continue

        printed_clean = re.sub(r"[^A-Z0-9]", "", printed_val.upper())
        mrz_clean = re.sub(r"[^A-Z0-9]", "", mrz_val.upper())

        if printed_clean != mrz_clean and printed_clean not in mrz_clean and mrz_clean not in printed_clean:
            flags.append(ValidationFlag(
                code="MRZ_PRINTED_MISMATCH",
                description=f"The {label} in the printed text ('{printed_val}') does not "
                            f"match the {label} found in the machine-readable zone "
                            f"('{mrz_val}'). A genuine document's MRZ and printed fields "
                            f"should always agree - this is a strong tampering signal.",
                severity="high",
            ))

    # Date fields: printed dates (e.g. DD/MM/YYYY) and MRZ dates (raw
    # YYMMDD) use different formats, so they must be parsed into actual
    # date objects before comparing - comparing the raw strings directly
    # would falsely flag every genuine document.
    date_checks = [
        ("date_of_expiry", "mrz_date_of_expiry", "expiry date", "future"),
        ("date_of_birth", "mrz_date_of_birth", "date of birth", "past"),
    ]

    for printed_key, mrz_key, label, bias in date_checks:
        printed_val = fields.get(printed_key)
        mrz_val = fields.get(mrz_key)
        if not printed_val or not mrz_val:
            continue

        printed_date = _try_parse_date(printed_val, mrz_year_bias=bias)
        mrz_date = _try_parse_date(mrz_val, mrz_year_bias=bias)

        if printed_date is None or mrz_date is None:
            continue  # unparseable dates are already flagged separately

        if printed_date != mrz_date:
            flags.append(ValidationFlag(
                code="MRZ_PRINTED_MISMATCH",
                description=f"The {label} in the printed text ('{printed_val}' = "
                            f"{printed_date.isoformat()}) does not match the {label} found "
                            f"in the machine-readable zone ('{mrz_val}' = "
                            f"{mrz_date.isoformat()}). A genuine document's MRZ and printed "
                            f"fields should always agree - this is a strong tampering signal.",
                severity="high",
            ))


def _check_missing_critical_fields(fields: dict, doc_type: str, flags: list[ValidationFlag]) -> None:
    critical_by_type = {
        "passport": ["name", "date_of_birth", "passport_number"],
        "visa": ["visa_number", "visa_type"],
        "national_id": ["name", "id_number"],
        "driving_license": ["name", "id_number"],
    }
    expected = critical_by_type.get(doc_type, [])
    missing = [f for f in expected if f not in fields and f"mrz_{f}" not in fields]

    if missing and len(missing) == len(expected) and expected:
        flags.append(ValidationFlag(
            code="NO_CRITICAL_FIELDS_FOUND",
            description=f"None of the expected critical fields for a {doc_type} "
                        f"({', '.join(expected)}) were found. This document may be "
                        f"unreadable, cropped incorrectly, or not actually match its "
                        f"guessed type.",
            severity="low",
        ))


def validate_document_fields(extracted_fields: dict, document_type: str) -> dict:
    """
    Main entry point. Validates a dict of extracted fields (as produced by
    ocr_extraction.extract_document_fields) and returns a risk report.
    """
    flags: list[ValidationFlag] = []

    _check_expiry_date(extracted_fields, flags)
    _check_date_of_birth(extracted_fields, flags)
    _check_passport_number_format(extracted_fields, document_type, flags)
    _check_field_consistency(extracted_fields, flags)
    _check_missing_critical_fields(extracted_fields, document_type, flags)

    risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))

    result = ValidationResult(
        document_type=document_type,
        fields_validated=len(extracted_fields),
        flags=flags,
        risk_score=risk_score,
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys
    import json
    from ocr_extraction import extract_document_fields

    if len(sys.argv) < 2:
        print("Usage: python document_validation.py <path_to_document_image>")
        sys.exit(1)

    extraction = extract_document_fields(sys.argv[1])
    validation = validate_document_fields(
        extraction["extracted_fields"], extraction["document_type_guess"]
    )

    print("=== Extracted Fields ===")
    print(json.dumps(extraction["extracted_fields"], indent=2))
    print("\n=== Validation Report ===")
    print(json.dumps(validation, indent=2, default=str))
