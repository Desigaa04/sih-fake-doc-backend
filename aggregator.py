"""
Aggregation & Scoring Module
SIH26188 - AI-Based Fake Identity & Document Screening System

This is the module that ties all 7 detection functions together into ONE
final, explainable verdict - structured to directly mirror the SIH problem
statement's official module breakdown:

    Module 1: OCR Extraction          -> ocr_extraction.py
    Module 2: Document Validation     -> document_validation.py
    Module 3: Tampering Detection     -> photo_replacement.py, text_manipulation.py,
                                          stamp_forgery.py, metadata_analysis.py
                                          (the 4 sub-checks SIH explicitly lists
                                          under this one module)
    Module 4: Face Verification       -> face_verification.py

Rather than just showing 7 separate pass/fail checks, this module:

1. Combines the 4 Module 3 (Tampering Detection) sub-checks into one
   tampering risk score first, since SIH treats them as one module.
2. Combines that, plus Module 2 and Module 4, into one final WEIGHTED
   score - some signals are stronger evidence of forgery than others
   (e.g. an MRZ vs printed-text mismatch is much stronger evidence than a
   slightly inconsistent font size), so they're weighted accordingly.
3. Produces a clear verdict band (Genuine / Needs Review / Likely Fake)
   instead of a raw number nobody can interpret. This IS the "risk score"
   the SIH problem statement explicitly asks for, to help border security
   personnel make faster decisions.
4. Surfaces the TOP reasons behind the verdict, sorted by severity, so a
   human reviewer immediately sees WHY a document was flagged.
5. Handles optional checks gracefully - face_verification and
   stamp_forgery only run when a selfie / stamp crop is provided, so the
   scoring adjusts its weight total accordingly rather than penalizing a
   document for missing an optional check.

This weighted, explainable combination logic is the core "backend
intelligence" contribution - the individual detectors give raw signals,
this module turns them into a decision a human can trust and act on.
"""

from __future__ import annotations

# --- Module 3 (Tampering Detection) internal sub-check weights ---
# How much each of the 4 tampering sub-checks contributes to Module 3's
# own combined score.
TAMPERING_SUB_WEIGHTS = {
    "photo_replacement": 1.1,     # strong tampering signal (ELA)
    "text_manipulation": 1.0,     # supporting signal
    "stamp_forgery": 0.9,         # supporting signal, limited by reference coverage
    "metadata_analysis": 0.8,     # supporting signal - easy to strip/fake, so weighted lower
}

# --- Top-level weights across the 3 scored modules (Module 1 has no
# risk_score of its own - it just extracts fields for Module 2 to check) ---
TOP_LEVEL_WEIGHTS = {
    "document_validation": 1.3,   # Module 2 - logical/format checks, very reliable
    "tampering_detection": 1.2,   # Module 3 - combined score from the 4 sub-checks
    "face_verification": 1.3,     # Module 4 - identity match, very reliable when available
}

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}

# Verdict thresholds on the final weighted risk score (0-100)
GENUINE_THRESHOLD = 25
REVIEW_THRESHOLD = 55


def _weighted_average(results_and_weights):
    """Given a list of (result_dict, weight) pairs, returns the weighted
    average of their risk_score fields. Skips any None results."""
    weighted_sum = 0.0
    weight_total = 0.0
    for result, weight in results_and_weights:
        if result is None:
            continue
        weighted_sum += result.get("risk_score", 0) * weight
        weight_total += weight
    return round(weighted_sum / weight_total, 1) if weight_total > 0 else 0.0


def aggregate_results(module_results: dict) -> dict:
    """
    Combines the raw outputs of all evaluated modules into one final
    report, grouped to match SIH's official Module 1-4 structure.

    module_results: dict keyed by the individual function/file names
    ("ocr_extraction", "document_validation", "photo_replacement",
    "text_manipulation", "stamp_forgery", "metadata_analysis",
    "face_verification") -> that check's own result dict. Only include
    keys for optional checks that were actually run (skip
    face_verification/stamp_forgery entirely if no selfie/stamp crop was
    provided).
    """
    all_flags = []

    # --- Module 3: Tampering Detection (combine its 4 sub-checks first) ---
    tampering_sub_results = {}
    tampering_pairs = []
    for sub_name, weight in TAMPERING_SUB_WEIGHTS.items():
        result = module_results.get(sub_name)
        tampering_sub_results[sub_name] = {
            "evaluated": result is not None,
            "risk_score": result.get("risk_score") if result else None,
        }
        if result is not None:
            tampering_pairs.append((result, weight))
            for flag_dict in result.get("flags", []):
                all_flags.append({**flag_dict, "source_module": sub_name})

    tampering_risk_score = _weighted_average(tampering_pairs)
    tampering_evaluated = len(tampering_pairs) > 0

    module_3_tampering_detection = {
        "risk_score": tampering_risk_score if tampering_evaluated else None,
        "sub_checks": tampering_sub_results,
    }

    # --- Module 2: Document Validation ---
    doc_validation_result = module_results.get("document_validation")
    if doc_validation_result:
        for flag_dict in doc_validation_result.get("flags", []):
            all_flags.append({**flag_dict, "source_module": "document_validation"})

    # --- Module 4: Face Verification ---
    face_result = module_results.get("face_verification")
    if face_result:
        for flag_dict in face_result.get("flags", []):
            all_flags.append({**flag_dict, "source_module": "face_verification"})

    # --- Combine Module 2 + Module 3 + Module 4 into the final risk score ---
    top_level_pairs = [
        (doc_validation_result, TOP_LEVEL_WEIGHTS["document_validation"]),
        (
            {"risk_score": tampering_risk_score} if tampering_evaluated else None,
            TOP_LEVEL_WEIGHTS["tampering_detection"],
        ),
        (face_result, TOP_LEVEL_WEIGHTS["face_verification"]),
    ]
    final_risk_score = _weighted_average(top_level_pairs)
    final_trust_score = round(100 - final_risk_score, 1)

    if final_risk_score < GENUINE_THRESHOLD:
        verdict = "Likely Genuine"
    elif final_risk_score < REVIEW_THRESHOLD:
        verdict = "Needs Manual Review"
    else:
        verdict = "Likely Fake"

    # Sort flags so the most severe, most important reasons appear first -
    # this is what a reviewer (or judge) should see right away.
    all_flags.sort(key=lambda f: SEVERITY_RANK.get(f.get("severity", "low"), 0), reverse=True)

    ocr_info = module_results.get("ocr_extraction", {})

    return {
        "verdict": verdict,
        "final_trust_score": final_trust_score,
        "final_risk_score": final_risk_score,
        "top_reasons": all_flags[:5],
        "all_flags": all_flags,
        "modules": {
            "module_1_ocr_extraction": {
                "document_type_guess": ocr_info.get("document_type_guess"),
                "extracted_fields": ocr_info.get("extracted_fields"),
                "mrz_detected": ocr_info.get("mrz_detected"),
                "warnings": ocr_info.get("warnings"),
                "raw_text": ocr_info.get("raw_text"),
            },
            "module_2_document_validation": {
                "evaluated": doc_validation_result is not None,
                "risk_score": doc_validation_result.get("risk_score") if doc_validation_result else None,
            },
            "module_3_tampering_detection": module_3_tampering_detection,
            "module_4_face_verification": {
                "evaluated": face_result is not None,
                "risk_score": face_result.get("risk_score") if face_result else None,
                "match_confidence": face_result.get("match_confidence") if face_result else None,
            },
        },
    }
