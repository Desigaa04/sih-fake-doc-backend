"""
Photo Replacement Detection Module
SIH26188 - AI-Based Fake Identity & Document Screening System

Detects whether part of a document image (most commonly the photo region,
but works for any pasted/edited region) was likely copy-pasted or edited in
from elsewhere, using a technique called Error Level Analysis (ELA).

--- How ELA works (plain explanation) ---
A JPEG image is saved using "lossy" compression - every time you save a
JPEG, it re-compresses the whole image and loses a small, consistent amount
of quality everywhere, uniformly.

If someone takes a genuine ID document, pastes in a different photo, and
saves it again, the newly-pasted region was compressed a DIFFERENT number
of times than the rest of the document (it came from a different original
file). This creates a difference in "error level" between the untouched
parts of the image and the edited part - even though it's invisible to the
human eye.

ELA re-compresses the image at a known quality level, then computes the
pixel-by-pixel difference between the original and the re-compressed
version. Untouched, consistently-compressed regions show a low, uniform
error level. Edited/pasted regions often show a noticeably different
(usually higher) and non-uniform error level - visible as brighter patches
in the ELA output image.

This is NOT proof of forgery by itself (a genuine document can have some
variation too, e.g. from stamps or signatures), but a strong, well-known
supporting signal - which is why the report gives a risk score with
supporting detail rather than a hard "fake/real" verdict, and is meant to
be combined with the other modules (metadata, text, stamp, face).

Usage:
    from photo_replacement import analyze_photo_replacement

    result = analyze_photo_replacement("path/to/document.jpg")
    print(result["risk_score"], result["flags"])
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

from PIL import Image, ImageChops
import numpy as np

# JPEG quality used for the ELA re-compression step. 90 is a commonly used
# value in ELA literature/tools - low enough to expose differences, high
# enough not to introduce noise from the analysis itself.
ELA_QUALITY = 90

# Image is divided into a grid of blocks; each block's average error level
# is compared against the image's overall average to find "hot spots".
BLOCK_SIZE = 16

# A block's error level needs to be at least this many times the image's
# average error level to be flagged as a suspicious hot spot.
HOTSPOT_THRESHOLD_MULTIPLIER = 2.5

# If this percentage (or more) of the image's area is made up of hot-spot
# blocks, it suggests a larger tampered region rather than noise.
SUSPICIOUS_AREA_PERCENT = 3.0


@dataclass
class PhotoReplacementFlag:
    code: str
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class PhotoReplacementResult:
    file_name: str
    flags: list[PhotoReplacementFlag] = field(default_factory=list)
    mean_error_level: float = 0.0
    max_error_level: float = 0.0
    suspicious_area_percent: float = 0.0
    risk_score: int = 0
    ela_image_path: str | None = None  # path to saved visual ELA output, if requested

    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "risk_score": self.risk_score,
            "mean_error_level": round(self.mean_error_level, 2),
            "max_error_level": round(self.max_error_level, 2),
            "suspicious_area_percent": round(self.suspicious_area_percent, 2),
            "flags": [
                {"code": f.code, "description": f.description, "severity": f.severity}
                for f in self.flags
            ],
            "ela_image_path": self.ela_image_path,
        }


SEVERITY_WEIGHTS = {"low": 10, "medium": 25, "high": 40}


def _compute_ela_image(image: Image.Image, quality: int = ELA_QUALITY) -> Image.Image:
    """
    Re-saves the image at a known JPEG quality in memory, then returns the
    pixel-difference image between the original and the re-saved version,
    scaled up for visibility.
    """
    rgb_image = image.convert("RGB")

    buffer = io.BytesIO()
    rgb_image.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer)

    ela_image = ImageChops.difference(rgb_image, recompressed)

    # Scale pixel differences up so they're visible/comparable - find the
    # max difference across all channels and scale so it maps to 255.
    extrema = ela_image.getextrema()
    max_diff = max(pair[1] for pair in extrema) if extrema else 1
    max_diff = max(max_diff, 1)  # avoid division by zero
    scale = 255.0 / max_diff

    ela_image = ela_image.point(lambda p: min(255, int(p * scale)))
    return ela_image


def _analyze_blocks(ela_image: Image.Image, block_size: int = BLOCK_SIZE):
    """
    Divides the ELA image into blocks and computes the average error level
    per block. Returns (block_means array, overall mean, overall max).
    """
    gray = ela_image.convert("L")
    arr = np.array(gray, dtype=np.float64)
    height, width = arr.shape

    block_means = []
    for y in range(0, height - block_size + 1, block_size):
        for x in range(0, width - block_size + 1, block_size):
            block = arr[y:y + block_size, x:x + block_size]
            block_means.append(block.mean())

    block_means = np.array(block_means) if block_means else np.array([0.0])
    overall_mean = float(arr.mean())
    overall_max = float(arr.max())

    return block_means, overall_mean, overall_max


def _flag_hotspots(block_means, overall_mean: float, flags: list[PhotoReplacementFlag]) -> float:
    """
    Finds blocks whose error level is much higher than the image average
    (potential pasted/edited regions) and flags if they cover a meaningful
    portion of the image. Returns the suspicious area percentage.
    """
    if overall_mean <= 0 or len(block_means) == 0:
        return 0.0

    threshold = overall_mean * HOTSPOT_THRESHOLD_MULTIPLIER
    hotspot_count = int(np.sum(block_means > threshold))
    suspicious_percent = (hotspot_count / len(block_means)) * 100

    if suspicious_percent >= SUSPICIOUS_AREA_PERCENT:
        severity = "high" if suspicious_percent >= 10 else "medium"
        flags.append(PhotoReplacementFlag(
            code="ELA_HOTSPOT_REGION",
            description=f"Detected a region covering approximately {suspicious_percent:.1f}% "
                        f"of the image with a compression error level significantly higher "
                        f"than the rest of the document. This pattern is commonly seen when "
                        f"a photo or region has been pasted in from a different source and "
                        f"re-saved.",
            severity=severity,
        ))

    return suspicious_percent


def _flag_overall_noise(overall_mean: float, overall_max: float, flags: list[PhotoReplacementFlag]) -> None:
    """
    A very high overall error level (not localized to one region) can
    indicate the whole image has been re-saved/re-compressed multiple
    times, which is a softer but still relevant tampering signal.
    """
    if overall_mean > 15:
        flags.append(PhotoReplacementFlag(
            code="HIGH_OVERALL_COMPRESSION_NOISE",
            description=f"The image shows a high overall compression error level "
                        f"(avg={overall_mean:.1f}), suggesting it may have been saved/"
                        f"re-compressed multiple times, which can happen during editing "
                        f"and re-exporting.",
            severity="low",
        ))


def analyze_photo_replacement(file_path: str, save_ela_visual: bool = True) -> dict:
    """
    Main entry point. Runs Error Level Analysis on the given document image
    and returns a risk report with flags explaining any suspicious regions
    found.

    If save_ela_visual is True, also saves a viewable ELA heatmap image
    next to the input file (named <original>_ela.jpg) - useful for showing
    judges a visual "here's what the AI saw" during your demo.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    file_name = os.path.basename(file_path)
    flags: list[PhotoReplacementFlag] = []

    with Image.open(file_path) as image:
        ela_image = _compute_ela_image(image)
        block_means, overall_mean, overall_max = _analyze_blocks(ela_image)

    suspicious_percent = _flag_hotspots(block_means, overall_mean, flags)
    _flag_overall_noise(overall_mean, overall_max, flags)

    risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))

    ela_path = None
    if save_ela_visual:
        base, ext = os.path.splitext(file_path)
        ela_path = f"{base}_ela.jpg"
        ela_image.save(ela_path, "JPEG")

    result = PhotoReplacementResult(
        file_name=file_name,
        flags=flags,
        mean_error_level=overall_mean,
        max_error_level=overall_max,
        suspicious_area_percent=suspicious_percent,
        risk_score=risk_score,
        ela_image_path=ela_path,
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python photo_replacement.py <path_to_image>")
        sys.exit(1)

    report = analyze_photo_replacement(sys.argv[1])
    print(json.dumps(report, indent=2, default=str))
    if report["ela_image_path"]:
        print(f"\nA visual ELA heatmap was saved to: {report['ela_image_path']}")
        print("Open that image to SEE the analysis - brighter/patchy areas indicate")
        print("possible edited regions. This is great to show in your demo.")
