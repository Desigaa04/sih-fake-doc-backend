# Fake Document Screening - Backend

Backend for SIH26188: AI-Based Fake Identity & Document Screening System.

## Folder structure

Make sure your project folder looks like this (all files in the SAME folder,
no subfolders needed):

```
sih-fake-doc-backend/
├── main.py                  <- API entry point
├── aggregator.py             <- combines all module results into one verdict
├── ocr_extraction.py          <- from your friend
├── document_validation.py     <- from your friend
├── text_manipulation.py       <- from your friend
├── photo_replacement.py       <- from your friend
├── face_verification.py       <- from your friend
├── stamp_forgery.py           <- from your friend
├── metadata_analysis.py       <- from your friend
├── requirements.txt
├── reference_stamps/          <- create this folder, add 3-5 sample genuine stamp images
└── .gitignore
```

## One-time setup

### 1. Install Python dependencies

Open a terminal in this folder (in VS Code: Terminal menu > New Terminal) and run:

```
pip install -r requirements.txt
```

### 2. Install Tesseract OCR (separate from the pip package - this is a REQUIRED system program)

`pytesseract` (the pip package) is just a thin wrapper - it needs the actual
Tesseract OCR program installed on your computer to work.

**Windows:**
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run it, install to the default location (usually `C:\Program Files\Tesseract-OCR`)
3. Set an environment variable so the code can find it:
   - Open Command Prompt and run:
     ```
     setx TESSERACT_CMD "C:\Program Files\Tesseract-OCR\tesseract.exe"
     ```
   - **Close and reopen VS Code/terminal** after this for it to take effect.

**Mac:**
```
brew install tesseract
```

**Linux:**
```
sudo apt install tesseract-ocr
```

### 3. Create the reference stamps folder

Create a folder named `reference_stamps` in this same directory, and add
3-5 sample images of genuine stamps/seals (cropped tightly to just the
stamp). This is what stamp_forgery.py compares against. If you don't have
real samples yet, you can leave it empty for now - the module will just
report "no reference stamps" instead of crashing.

## Running the backend

```
uvicorn main:app --reload
```

You should see it start on `http://127.0.0.1:8000`.

## Testing it (no frontend needed yet!)

Open this URL in your browser:

```
http://127.0.0.1:8000/docs
```

This is an auto-generated interactive test page. Click on `POST /screen-document`,
click "Try it out", upload a document image (and optionally a selfie / stamp
crop), and click Execute. You'll see the full JSON verdict right there.

This is genuinely useful for your demo too, in case the frontend isn't ready -
you can screen-share this page and run live documents through it.

## What the API returns

A single JSON object with:
- `verdict`: "Likely Genuine" / "Needs Manual Review" / "Likely Fake"
- `final_trust_score`: 0-100 (higher = more trustworthy)
- `top_reasons`: the most important flags explaining the verdict
- `module_breakdown`: each module's individual score
- `extracted_fields`: the name, DOB, ID number etc. that were read off the document

## Connecting the frontend

Share this with whoever is building the frontend:
- Endpoint: `POST http://127.0.0.1:8000/screen-document`
- Body: multipart/form-data with fields `document` (required file), `selfie`
  (optional file), `stamp_crop` (optional file)
- Response: JSON, shape described above
