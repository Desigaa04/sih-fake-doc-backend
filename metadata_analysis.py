"""
Metadata Analysis Module
SIH26188 - AI-Based Fake Identity & Document Screening System

Reads image metadata (EXIF) and file-level properties to flag signs that a
document image may have been edited, screenshotted, re-saved, or generated
by editing software rather than being a genuine scan/photo of a document.

This module does NOT use AI/ML - it's rule-based metadata inspection, which
makes it fast, explainable, and a good first line of defense before the
heavier modules (photo replacement, text manipulation, etc.) run.

Usage:
    from metadata_analysis import analyze_metadata

    result = analyze_metadata("path/to/document.jpg")
    print(result["risk_score"], result["flags"])
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS

# Software tags commonly left behind by image editors. If present, it's a
# strong (but not certain - legitimate scanning software can also appear
# here) signal of post-processing.
SUSPICIOUS_SOFTWARE_KEYWORDS = [
    "photoshop", "gimp", "lightroom", "snapseed", "picsart",
    "pixlr", "canva", "affinity photo", "paint.net", "photopea",
]

# Editing apps sometimes leave no camera make/model at all, which is
# unusual for a genuine phone photo/scan of a physical document.
EXPECTED_CAMERA_TAGS = ["Make", "Model"]


@dataclass
class MetadataFlag:
    code: str
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class MetadataResult:
    file_name: str
    flags: list[MetadataFlag] = field(default_factory=list)
    raw_exif: dict = field(default_factory=dict)
    risk_score: int = 0  # 0 (clean) - 100 (highly suspicious)

    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "risk_score": self.risk_score,
            "flags": [
                {"code": f.code, "description": f.description, "severity": f.severity}
                for f in self.flags
            ],
            "raw_exif": self.raw_exif,
        }


# Severity -> points added to risk score
SEVERITY_WEIGHTS = {"low": 10, "medium": 25, "high": 40}


def _extract_exif(image: Image.Image) -> dict:
    """Extract raw EXIF tags as a readable {tag_name: value} dict."""
    exif_data = {}
    try:
        raw = image.getexif()
        if raw:
            for tag_id, value in raw.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                # Keep values JSON/repr friendly
                if isinstance(value, bytes):
                    try:
                        value = value.decode(errors="replace")
                    except Exception:
                        value = repr(value)
                exif_data[tag_name] = value
    except Exception:
        pass
    return exif_data


def _check_editing_software(exif: dict, flags: list[MetadataFlag]) -> None:
    software = str(exif.get("Software", "")).lower()
    if not software:
        return
    for keyword in SUSPICIOUS_SOFTWARE_KEYWORDS:
        if keyword in software:
            flags.append(MetadataFlag(
                code="EDITING_SOFTWARE_DETECTED",
                description=f"Image metadata shows it was processed with '{exif.get('Software')}', "
                            f"a known photo-editing tool.",
                severity="high",
            ))
            return


def _check_missing_camera_info(exif: dict, flags: list[MetadataFlag]) -> None:
    missing = [tag for tag in EXPECTED_CAMERA_TAGS if tag not in exif]
    if len(missing) == len(EXPECTED_CAMERA_TAGS):
        flags.append(MetadataFlag(
            code="NO_CAMERA_INFO",
            description="No camera make/model found in metadata. Genuine phone photos or "
                        "scans usually retain this; its absence can indicate the image was "
                        "edited, screenshotted, or re-saved (which strips this data).",
            severity="low",
        ))


def _check_timestamp_consistency(exif: dict, flags: list[MetadataFlag]) -> None:
    """
    Compares 'DateTimeOriginal' (when the photo was actually taken) against
    'DateTime' (when the file was last modified/saved). A large or
    unexpected gap between these can indicate the image was edited well
    after it was originally captured.
    """
    original = exif.get("DateTimeOriginal") or exif.get("DateTime")
    modified = exif.get("DateTime")

    if not original or not modified:
        return

    try:
        fmt = "%Y:%m:%d %H:%M:%S"
        dt_original = datetime.strptime(original, fmt)
        dt_modified = datetime.strptime(modified, fmt)
        gap = abs((dt_modified - dt_original).total_seconds())

        # More than 1 hour between "taken" and "modified" timestamps is
        # unusual for an unedited photo (small gaps happen from normal
        # camera processing/save operations).
        if gap > 3600:
            flags.append(MetadataFlag(
                code="TIMESTAMP_MISMATCH",
                description=f"Large gap ({gap / 3600:.1f} hours) between when the photo was "
                            f"taken ({original}) and when it was last modified ({modified}). "
                            f"This can indicate the file was edited after capture.",
                severity="medium",
            ))
    except (ValueError, TypeError):
        # Timestamps present but not in the expected format - not treated
        # as suspicious on its own, just skipped.
        pass


def _check_resolution_anomalies(image: Image.Image, exif: dict, flags: list[MetadataFlag]) -> None:
    """
    Flags unusually low resolution (common in re-saved/re-compressed/
    screenshotted images, which lose quality) or resolution that doesn't
    match typical document-scan dimensions.
    """
    width, height = image.size
    total_pixels = width * height

    # Very low resolution is a common trait of screenshots of screenshots,
    # or heavily re-compressed forwarded images (e.g. via messaging apps).
    if total_pixels < 300_000:  # roughly smaller than 640x480
        flags.append(MetadataFlag(
            code="LOW_RESOLUTION",
            description=f"Image resolution is unusually low ({width}x{height}). This can "
                        f"indicate the file has been re-saved, re-compressed, or is a "
                        f"screenshot of another image rather than an original scan/photo.",
            severity="low",
        ))


def _check_file_format_consistency(file_path: str, image: Image.Image, flags: list[MetadataFlag]) -> None:
    """
    Flags a mismatch between the file extension and the actual detected
    image format (e.g. a file named 'id.jpg' that is actually a PNG
    internally) - a common trace left by some editing/conversion tools.
    """
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    actual_format = (image.format or "").lower()

    ext_to_format = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
    expected_format = ext_to_format.get(ext)

    if expected_format and actual_format and expected_format != actual_format:
        flags.append(MetadataFlag(
            code="FORMAT_MISMATCH",
            description=f"File has a '.{ext}' extension but its actual internal format is "
                        f"'{actual_format.upper()}'. This mismatch can happen when a file is "
                        f"converted or re-saved by editing software.",
            severity="low",
        ))


def analyze_metadata(file_path: str) -> dict:
    """
    Main entry point. Runs all metadata checks on the given image file and
    returns a dict report with a risk_score (0-100) and a list of flags
    explaining what was found and why it matters.

    This is designed to be one input into the overall document authenticity
    score computed by the integration layer (alongside photo replacement,
    text manipulation, stamp, and face verification modules) - it should
    NOT be used alone to make a final fake/genuine decision.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file: {file_path}")

    file_name = os.path.basename(file_path)
    flags: list[MetadataFlag] = []

    with Image.open(file_path) as image:
        exif = _extract_exif(image)

        _check_editing_software(exif, flags)
        _check_missing_camera_info(exif, flags)
        _check_timestamp_consistency(exif, flags)
        _check_resolution_anomalies(image, exif, flags)
        _check_file_format_consistency(file_path, image, flags)

    # Risk score = sum of severity weights, capped at 100
    risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in flags))

    result = MetadataResult(
        file_name=file_name,
        flags=flags,
        raw_exif=exif,
        risk_score=risk_score,
    )

    return result.to_dict()


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python metadata_analysis.py <path_to_image>")
        sys.exit(1)

    report = analyze_metadata(sys.argv[1])
    print(json.dumps(report, indent=2, default=str))
