"""
Generates two synthetic demo passports for the MRZ checksum demo:
  demo_passport_genuine.png  - MRZ with fully valid ICAO 9303 check digits
  demo_passport_tampered.png - identical image EXCEPT one DOB digit in MRZ
                               line 2 (12 -> 13) without recomputing the
                               check digit - exactly what a careless forger
                               produces (printed text is changed too, so the
                               MRZ-vs-printed consistency check does NOT fire
                               and the checksum flag is the differentiator).
Throwaway demo helper; not part of the screening pipeline.

Rendered at 1400px wide with large final-resolution MRZ glyphs (no
downsampling) because Tesseract misreads small anti-aliased monospace text
(0 -> @, phantom digits inserted). A self-check at the end prints what
Tesseract actually reads back from each image.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytesseract
if os.environ.get("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

from PIL import Image, ImageDraw, ImageFont
from mrz_validation import calculate_check_digit

passport_number = "M1234568"   # check digit 3 (avoids OCR-hostile 0/1 in the check-digit slot)
nationality = "IND"
dob = "900312"          # YYMMDD (12 March 1990) - check digit 9
sex = "M"
expiry = "300415"       # 15 April 2030 - check digit 7

W, H = 1400, 620
MRZ_H = 190


def build_mrz_line2():
    pf = passport_number + "<"  # ICAO pads the passport-number field to 9 chars
    pf_chk = str(calculate_check_digit(passport_number))
    dob_chk = str(calculate_check_digit(dob))
    exp_chk = str(calculate_check_digit(expiry))
    composite = pf + pf_chk + nationality + dob + dob_chk + sex + expiry + exp_chk
    filler = "P" * (43 - len(composite))
    # ICAO 9303 composite: weighted sum over l2[0:10] + l2[13:20] + l2[21:43]
    composite_data = pf + pf_chk + dob + dob_chk + expiry + exp_chk + filler
    return composite + filler + str(calculate_check_digit(composite_data))


def build_mrz_line1():
    name = "SHARMA<<RAHUL<"
    return "P<IND" + name + "<" * (44 - 5 - len(name))


def render(path, mrz_line1, mrz_line2, printed_dob, printed_expiry):
    img = Image.new("RGB", (W, H), (244, 242, 235))
    d = ImageDraw.Draw(img)

    def font(sz, bold=False):
        for name in (["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf"]):
            try:
                return ImageFont.truetype(name, sz)
            except OSError:
                continue
        return ImageFont.load_default()

    def mono(sz):
        for name in ("consola.ttf", "cour.ttf", "lucon.ttf"):
            try:
                return ImageFont.truetype(name, sz)
            except OSError:
                continue
        return ImageFont.load_default()

    d.rectangle([0, 0, W, 70], fill=(11, 61, 92))
    d.text((24, 18), "REPUBLIC OF INDIA  -  PASSPORT", font=font(32, True), fill="white")

    d.text((24, 100), "Type / Code / Passport No.", font=font(16), fill=(90, 90, 90))
    d.text((24, 126), "P  IND  " + passport_number, font=font(28, True), fill=(20, 20, 20))
    d.text((24, 185), "SURNAME / GIVEN NAME", font=font(16), fill=(90, 90, 90))
    d.text((24, 211), "SHARMA / RAHUL", font=font(28, True), fill=(20, 20, 20))
    d.text((24, 270), "Nationality", font=font(16), fill=(90, 90, 90))
    d.text((24, 296), "INDIAN", font=font(26, True), fill=(20, 20, 20))
    d.text((24, 355), "Sex", font=font(16), fill=(90, 90, 90))
    d.text((24, 381), "M", font=font(26, True), fill=(20, 20, 20))
    d.text((160, 355), "Date of Birth", font=font(16), fill=(90, 90, 90))
    d.text((160, 381), printed_dob, font=font(26, True), fill=(20, 20, 20))
    d.text((450, 355), "Date of Expiry", font=font(16), fill=(90, 90, 90))
    d.text((450, 381), printed_expiry, font=font(26, True), fill=(20, 20, 20))

    d.rectangle([760, 90, 1360, 450], outline=(150, 150, 150), width=3)
    d.ellipse([910, 180, 1090, 360], outline=(120, 120, 120), width=3)

    # MRZ zone: final-resolution, large, pure black on pure white
    d.rectangle([0, H - MRZ_H, W, H], fill=(255, 255, 255))
    m = mono(44)
    d.text((30, H - MRZ_H + 22), mrz_line1, font=m, fill=(0, 0, 0))
    d.text((30, H - MRZ_H + 104), mrz_line2, font=m, fill=(0, 0, 0))
    img.save(path)
    print("wrote", path)


if __name__ == "__main__":
    l1 = build_mrz_line1()
    l2 = build_mrz_line2()
    assert l2[43] == str(calculate_check_digit(l2[0:10] + l2[13:20] + l2[21:43])), "composite wrong"
    assert len(l1) == 44 and len(l2) == 44, (len(l1), len(l2))

    render("demo_passport_genuine.png", l1, l2, "12/03/1990", "15/04/2030")

    # Tampered twin: DOB day 12 -> 13 (printed AND MRZ), check digit NOT recomputed
    tampered_l2 = l2[:18] + "3" + l2[19:]
    # indices 17-18 are the DOB day '12'; replacing index 18 gives day '13'
    assert tampered_l2 != l2 and tampered_l2[18] == "3" and l2[18] == "2"
    render("demo_passport_tampered.png", l1, tampered_l2, "13/03/1990", "15/04/2030")

    print("\n--- Tesseract read-back self-check ---")
    for name in ("demo_passport_genuine.png", "demo_passport_tampered.png"):
        txt = pytesseract.image_to_string(Image.open(name))
        mrz = [l.strip().replace(" ", "") for l in txt.splitlines()
               if l.strip().replace(" ", "") and ("<" in l or l.strip().replace(" ", "").startswith(("P", "M")))]
        long_lines = [l for l in mrz if len(l) >= 30]
        print(name, "->", long_lines if long_lines else "(no MRZ-like lines)")
