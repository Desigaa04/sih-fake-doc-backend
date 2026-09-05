"""
Stamp/Seal Forgery Detection Module
SIH26188 - AI-Based Fake Identity & Document Screening System

Checks whether a stamp/seal on a document matches a set of known genuine
reference stamps, to catch forged, copy-pasted, or crudely faked official
stamps.

--- Approach ---
Uses ORB (Oriented FAST and Rotated BRIEF) feature matching, a classical
computer vision technique built into OpenCV (no internet/model download
needed):

1. ORB detects distinctive "keypoints" in an image (corners, edges,
   distinctive patterns) - the kind of fine detail present in an official
   stamp's design (text, emblem, border pattern).
2. It describes each keypoint with a compact numerical "descriptor".
3. To compare two stamps, we match descriptors between them - a genuine
   stamp of the same type will share many strong matching keypoints with
   its reference image (since it's a mechanical/digital stamp reproduced
   consistently). A forged/hand-drawn/mismatched stamp will share far
   fewer good matches.

This module expects a folder of reference "genuine" stamp images to
compare against (e.g. cropped photos of real institutional stamps you've
collected). For the hackathon prototype, 3-5 sample reference images is
enough to demonstrate the concept.

Important scope note: this module compares a STAMP REGION, not a full
document. For a full pipeline, you'd first detect/crop the stamp region
on the document (e.g. by asking the user to mark it, or with a simple
object detector) - for the hackathon demo, the simplest approach is to
have the user upload/crop just the stamp region directly, or accept a
bounding box. This prototype assumes the input image IS the stamp region
(already cropped), which keeps the demo simple and honest about scope.

Usage:
    from stamp_forgery import analyze_stamp_forgery

    result = analyze_stamp_forgery("path/to/stamp_crop.jpg", "reference_stamps/")
    print(result["risk_score"], result["best_match_confidence"])
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import cv2
import numpy as np

# Minimum number of "good" keypoint matches needed to consider two stamps
# a plausible match at all - below this, matching is unreliable/noise.
MIN_GOOD_MATCHES = 8

# Match confidence (0-100) below this is flagged as likely forged/mismatched.
MATCH_CONFIDENCE_THRESHOLD = 40

# Lowe's ratio test threshold for filtering good matches from ORB/BFMatcher
# (standard technique to discard ambiguous/weak matches).
RATIO_TEST_THRESHOLD = 0.75

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")


@dataclass
class StampFlag:
    code: str
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class StampForgeryResult:
    file_name: str
    reference_count: int = 0
    best_match_reference: str | None = None
    best_match_confidence: float = 0.0
    flags: list = field(default_factory=list)
    risk_score: int = 0

    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "reference_count": self.reference_count,
            "best_match_reference": self.best_match_reference,
            "best_match_confidence": round(self.best_match_confidence, 1),
            "risk_score": self.risk_score,
            "flags": [
                {"code": f.code, "description": f.description, "severity": f.severity}
                for f in self.flags
            ],
        }


SEVERITY_WEIGHTS = {"low": 10, "medium": 25, "high": 40}

_orb = cv2.ORB_create(nfeatures=1000)
_matcher = cv2.BFMatcher(cv2.NORM_HAMMING)


def _load_grayscale(path: str) -> np.ndarray | None:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return img


def _compute_match_confidence(img_a: np.ndarray, img_b: np.ndarray) -> tuple[float, int]:
    """
    Runs ORB feature detection + matching between two grayscale images and
    returns (match_confidence 0-100, number_of_good_matches).
    """
    kp_a, des_a = _orb.detectAndCompute(img_a, None)
    kp_b, des_b = _orb.detectAndCompute(img_b, None)

    if des_a is None or des_b is None or len(kp_a) == 0 or len(kp_b) == 0:
        return 0.0, 0

    # knnMatch with k=2 lets us apply Lowe's ratio test to filter out weak/
    # ambiguous matches, which is standard practice for ORB/SIFT matching.
    try:
        raw_matches = _matcher.knnMatch(des_a, des_b, k=2)
    except cv2.error:
        return 0.0, 0

    good_matches = []
    for match_pair in raw_matches:
        if len(match_pair) != 2:
            continue
        m, n = match_pair
        if m.distance < RATIO_TEST_THRESHOLD * n.distance:
            good_matches.append(m)

    num_good = len(good_matches)

    # Confidence scales with how many good matches were found relative to
    # the smaller of the two keypoint sets (so a small reference stamp
    # isn't unfairly penalized against a keypoint-rich input image).
    max_possible = max(1, min(len(kp_a), len(kp_b)))
    confidence = min(100.0, (num_good / max_possible) * 100 * 2.5)
    # The *2.5 scaling accounts for the fact that even strong genuine
    # matches rarely match >40% of all keypoints (stamps have repeated/
    # ambiguous patterns like plain borders) - tune this against your
    # actual reference data before the demo for better calibration.

    return confidence, num_good


def _load_reference_stamps(reference_folder: str) -> list[tuple[str, np.ndarray]]:
    references = []
    if not os.path.isdir(reference_folder):
        return references

    for fname in sorted(os.listdir(reference_folder)):
        if fname.lower().endswith(SUPPORTED_EXTENSIONS):
            path = os.path.join(reference_folder, fname)
            img = _load_grayscale(path)
            if img is not None:
                references.append((fname, img))

    return references


def analyze_stamp_forgery(file_path: str, reference_folder: str) -> dict:
    """
    Main entry point. Compares the stamp image at file_path against every
    reference stamp image in reference_folder using ORB feature matching,
    and returns a risk report based on the BEST match found (i.e. "does
    this stamp convincingly match ANY known genuine stamp type").

    This should be used as ONE input into the overall document
    authenticity score, alongside the other modules - a low match
    confidence flags the stamp for human review rather than an automatic
    rejection, since reference coverage in a prototype is necessarily
    limited (only stamps you've collected samples of can be matched).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    file_name = os.path.basename(file_path)
    flags: list[StampFlag] = []

    input_img = _load_grayscale(file_path)
    if input_img is None:
        flags.append(StampFlag(
            code="IMAGE_UNREADABLE",
            description="Could not read the provided image file for stamp analysis.",
            severity="high",
        ))
        risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))
        result = StampForgeryResult(file_name=file_name, flags=flags, risk_score=risk_score)
        return result.to_dict()

    references = _load_reference_stamps(reference_folder)

    if not references:
        flags.append(StampFlag(
            code="NO_REFERENCE_STAMPS",
            description=f"No reference stamp images were found in '{reference_folder}'. "
                        f"Add sample genuine stamp images to this folder to enable "
                        f"comparison - without references, forgery cannot be assessed.",
            severity="low",
        ))
        risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))
        result = StampForgeryResult(
            file_name=file_name, reference_count=0, flags=flags, risk_score=risk_score
        )
        return result.to_dict()

    best_confidence = 0.0
    best_reference_name = None
    best_good_matches = 0

    for ref_name, ref_img in references:
        confidence, num_good = _compute_match_confidence(input_img, ref_img)
        if confidence > best_confidence:
            best_confidence = confidence
            best_reference_name = ref_name
            best_good_matches = num_good

    if best_good_matches < MIN_GOOD_MATCHES:
        flags.append(StampFlag(
            code="INSUFFICIENT_KEYPOINT_MATCHES",
            description=f"Very few distinctive matching features ({best_good_matches}) "
                        f"were found between this stamp and any reference stamp. This can "
                        f"indicate the stamp design doesn't match a known genuine stamp, "
                        f"OR that image quality is too low for reliable comparison.",
            severity="medium",
        ))
    elif best_confidence < MATCH_CONFIDENCE_THRESHOLD:
        flags.append(StampFlag(
            code="LOW_STAMP_MATCH_CONFIDENCE",
            description=f"The best match found (against '{best_reference_name}') has a low "
                        f"confidence score ({best_confidence:.1f}%). This may indicate the "
                        f"stamp is forged, altered, or of a type not in our reference set - "
                        f"manual review recommended.",
            severity="medium",
        ))

    risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))

    result = StampForgeryResult(
        file_name=file_name,
        reference_count=len(references),
        best_match_reference=best_reference_name,
        best_match_confidence=best_confidence,
        flags=flags,
        risk_score=risk_score,
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python stamp_forgery.py <path_to_stamp_image> <reference_folder>")
        sys.exit(1)

    report = analyze_stamp_forgery(sys.argv[1], sys.argv[2])
    print(json.dumps(report, indent=2, default=str))
