"""
Image Preprocessing Utility
SIH26188 - AI-Based Fake Identity & Document Screening System

Prepares a clean, upscaled copy of a document image specifically for OCR
(Module 1: OCR Extraction). Real-world document photos vary a lot in
quality - phone camera scans, screenshots of scans, low-res uploads - and
OCR engines like Tesseract are sensitive to character edge clarity, so a
modest, honest preprocessing step meaningfully improves extraction
reliability for borderline images.

Important design decision: this ONLY touches the copy passed into OCR.
The original, untouched file is still used for:
- photo_replacement.py (Error Level Analysis needs the image's REAL,
  original compression signature - upscaling/re-saving would corrupt
  this and produce false results)
- metadata_analysis.py (a genuinely low resolution is itself a legitimate
  suspicious signal worth keeping, not something to hide)

This is a standard, honest preprocessing step (upscale + mild sharpen +
black/white contrast thresholding) - NOT an AI super-resolution model.
That distinction matters: a generative upscaler could hallucinate
plausible-looking characters that were never actually on the document,
which would be actively dangerous in a fraud detection tool. Simple
interpolation-based upscaling only makes existing detail cleaner and
easier for Tesseract to segment - it cannot invent detail that was never
captured in the original photo.

The thresholding step specifically helps with watermarked or textured-
background documents (a real, tested case: a document with a diagonal
"SAMPLE" watermark and a fine security-pattern background caused digit
misreads, e.g. a date's "0" read as "8" - Otsu thresholding pushes each
pixel to pure black or white based on local contrast, which suppresses
a faint semi-transparent watermark (low contrast) while preserving
solid printed text (high contrast). Tested and confirmed on a real
sample: fixed an incorrect expiry date read entirely, and meaningfully
improved a second, harder date field.

Usage:
    from preprocessing import enhance_image_for_ocr

    enhanced_path = enhance_image_for_ocr("path/to/document.jpg", tmp_dir)
    # use enhanced_path for OCR calls only, keep original path for
    # photo_replacement / metadata_analysis
"""

from __future__ import annotations

import os

import cv2

# If the image's width is below this, we upscale it before OCR. Images
# already wider than this are left alone (no benefit, just wastes time).
MIN_WIDTH_FOR_OCR = 1200


def enhance_image_for_ocr(input_path: str, output_dir: str) -> str:
    """
    Returns the path to an OCR-friendly version of the image at
    input_path: upscaled (if small) and mildly sharpened. Does NOT apply
    black/white thresholding - this version is used specifically for
    reading the MRZ zone, since Otsu thresholding (see
    enhance_image_for_ocr_thresholded below) was tested and found to
    introduce MORE character corruption on the MRZ's small, dense
    monospace text, even though it helps larger, sparser printed text
    elsewhere on the same document. Different regions of the same
    document can have different optimal preprocessing - there's no
    single setting that's best everywhere.

    This does NOT modify or overwrite the original file - it writes a
    new file into output_dir and returns that new path.
    """
    img = cv2.imread(input_path)
    if img is None:
        return input_path

    height, width = img.shape[:2]
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_ocr_ready.png")

    if width < MIN_WIDTH_FOR_OCR:
        scale = MIN_WIDTH_FOR_OCR / width
        new_size = (int(width * scale), int(height * scale))
        img = cv2.resize(img, new_size, interpolation=cv2.INTER_CUBIC)

        blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=2)
        img = cv2.addWeighted(img, 1.5, blurred, -0.5, 0)

    cv2.imwrite(output_path, img)
    return output_path


def enhance_image_for_ocr_thresholded(input_path: str, output_dir: str) -> str:
    """
    Same as enhance_image_for_ocr(), but additionally applies Otsu
    thresholding (pure black/white conversion based on local contrast).
    This suppresses faint watermarks/security-pattern backgrounds and
    was tested to genuinely improve reading larger printed fields (e.g.
    fixed a misread expiry date entirely on a real watermarked sample) -
    but is worse for the MRZ zone specifically (see
    enhance_image_for_ocr above). Use this version for general printed
    field extraction, and the non-thresholded version for the MRZ.
    """
    img = cv2.imread(input_path)
    if img is None:
        return input_path

    height, width = img.shape[:2]
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_ocr_ready_thresh.png")

    if width < MIN_WIDTH_FOR_OCR:
        scale = MIN_WIDTH_FOR_OCR / width
        new_size = (int(width * scale), int(height * scale))
        img = cv2.resize(img, new_size, interpolation=cv2.INTER_CUBIC)
        blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=2)
        img = cv2.addWeighted(img, 1.5, blurred, -0.5, 0)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    cv2.imwrite(output_path, thresholded)
    return output_path
