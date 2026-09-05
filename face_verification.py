"""
Face Verification Module
SIH26188 - AI-Based Fake Identity & Document Screening System

Compares the photo on an ID document against a second photo (e.g. a live
selfie taken at the point of verification) to check if they show the same
person.

--- Approach ---
This prototype uses classical computer vision rather than a deep-learning
face recognition model (like FaceNet/ArcFace), because those require
downloading large pretrained weight files from the internet, which may not
be available in every setup. This approach is honest about being a lighter
prototype-grade check, not production-grade face recognition - which is a
reasonable, explainable limitation to state in your pitch.

Pipeline:
1. Detect the face region in both images using OpenCV's Haar Cascade
   face detector (fast, built into OpenCV, no internet/model download
   needed).
2. Crop and align both faces to the same size.
3. Compare them using two complementary similarity measures:
   a. Structural Similarity Index (SSIM) - measures perceptual/structural
      similarity between the two face images.
   b. Histogram correlation - compares the distribution of pixel
      intensities, robust to small lighting differences.
4. Combine both into a single match confidence score.

Note: this approach is sensitive to pose, lighting, and image quality
differences more than a deep-learning model would be. It's suitable for a
hackathon demo showing the concept and pipeline, not for production KYC
use - the report explicitly says so, and a real deployment would swap in
a proper face recognition model (e.g. via DeepFace or face_recognition
libraries) using this same function signature.

Usage:
    from face_verification import analyze_face_verification

    result = analyze_face_verification("id_photo.jpg", "selfie.jpg")
    print(result["risk_score"], result["match_confidence"])
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

FACE_SIZE = (200, 200)  # faces are resized to this before comparison

# Below this match confidence (0-100), we flag a likely mismatch.
MATCH_CONFIDENCE_THRESHOLD = 55

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


@dataclass
class FaceFlag:
    code: str
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class FaceVerificationResult:
    id_photo_name: str
    selfie_name: str
    faces_detected: bool = False
    match_confidence: float = 0.0
    flags: list = field(default_factory=list)
    risk_score: int = 0

    def to_dict(self) -> dict:
        return {
            "id_photo_name": self.id_photo_name,
            "selfie_name": self.selfie_name,
            "faces_detected": self.faces_detected,
            "match_confidence": round(self.match_confidence, 1),
            "risk_score": self.risk_score,
            "flags": [
                {"code": f.code, "description": f.description, "severity": f.severity}
                for f in self.flags
            ],
        }


SEVERITY_WEIGHTS = {"low": 10, "medium": 25, "high": 40}


def _detect_largest_face(image_path: str):
    """
    Loads an image and returns the cropped, grayscale, resized face region
    (the largest detected face, in case of multiple faces in frame), or
    None if no face was found.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )

    if len(faces) == 0:
        return None

    # Pick the largest detected face (by area) - most likely the primary
    # subject rather than a background face.
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face_crop = gray[y:y + h, x:x + w]
    face_resized = cv2.resize(face_crop, FACE_SIZE)
    return face_resized


def _compare_faces(face_a: np.ndarray, face_b: np.ndarray) -> float:
    """
    Compares two aligned, grayscale face images and returns a match
    confidence score from 0-100, combining structural similarity and
    histogram correlation.
    """
    # Structural similarity (perceptual/structural match)
    ssim_score = ssim(face_a, face_b)  # ranges -1 to 1, typically 0-1

    # Histogram correlation (robust to lighting differences)
    hist_a = cv2.calcHist([face_a], [0], None, [256], [0, 256])
    hist_b = cv2.calcHist([face_b], [0], None, [256], [0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    hist_score = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)  # -1 to 1

    # Combine: weight structural similarity higher, since it captures
    # facial geometry better than raw pixel-intensity distribution.
    combined = (0.7 * ssim_score) + (0.3 * hist_score)
    confidence = max(0.0, min(100.0, combined * 100))
    return confidence


def analyze_face_verification(id_photo_path: str, selfie_path: str) -> dict:
    """
    Main entry point. Detects faces in both the ID photo and the selfie,
    compares them, and returns a risk report.

    This should be used as ONE input into the overall document
    authenticity score, alongside metadata, photo replacement, text
    manipulation, and stamp forgery checks - a low match confidence here
    should prompt human review, not an automatic rejection.
    """
    for path in (id_photo_path, selfie_path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"No such file: {path}")

    id_photo_name = os.path.basename(id_photo_path)
    selfie_name = os.path.basename(selfie_path)
    flags: list[FaceFlag] = []

    face_a = _detect_largest_face(id_photo_path)
    face_b = _detect_largest_face(selfie_path)

    if face_a is None or face_b is None:
        missing = []
        if face_a is None:
            missing.append("ID photo")
        if face_b is None:
            missing.append("selfie")
        flags.append(FaceFlag(
            code="FACE_NOT_DETECTED",
            description=f"No face could be detected in the: {', '.join(missing)}. "
                        f"This can happen with low image quality, unusual angles, "
                        f"or poor lighting - please retake with the face clearly "
                        f"visible and well-lit.",
            severity="high",
        ))
        risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))
        result = FaceVerificationResult(
            id_photo_name=id_photo_name,
            selfie_name=selfie_name,
            faces_detected=False,
            match_confidence=0.0,
            flags=flags,
            risk_score=risk_score,
        )
        return result.to_dict()

    confidence = _compare_faces(face_a, face_b)

    if confidence < MATCH_CONFIDENCE_THRESHOLD:
        severity = "high" if confidence < 35 else "medium"
        flags.append(FaceFlag(
            code="LOW_FACE_MATCH_CONFIDENCE",
            description=f"The face in the ID photo and the provided selfie have a low "
                        f"similarity score ({confidence:.1f}%). This may indicate the "
                        f"photos show different people, or could be due to lighting/angle "
                        f"differences - manual review recommended.",
            severity=severity,
        ))

    risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))

    result = FaceVerificationResult(
        id_photo_name=id_photo_name,
        selfie_name=selfie_name,
        faces_detected=True,
        match_confidence=confidence,
        flags=flags,
        risk_score=risk_score,
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python face_verification.py <id_photo_path> <selfie_path>")
        sys.exit(1)

    report = analyze_face_verification(sys.argv[1], sys.argv[2])
    print(json.dumps(report, indent=2, default=str))
