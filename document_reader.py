import os
import sys
import tempfile
import requests
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

# ------------------------------------------------------------------
#  CONFIGURATION
# ------------------------------------------------------------------
CLOUD_NAME   = "dahxzrghh"
UPLOAD_PRESET = "LAW_office2026"
CLOUDINARY_URL = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/upload"

# ------------------------------------------------------------------
#  TEXT EXTRACTION
# ------------------------------------------------------------------
def extract_text_from_pdf(file_stream):
    """Try to extract text directly from a PDF using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"PyPDF2 extraction failed: {e}")
        return ""

def ocr_pdf(file_path):
    """Convert PDF pages to images and OCR with Tesseract."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(file_path, dpi=200)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img, lang='eng') + "\n"
        return text.strip()
    except Exception as e:
        print(f"OCR failed: {e}")
        return ""

def ocr_image(file_path):
    """OCR a single image file."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(file_path)
        return pytesseract.image_to_string(img, lang='eng').strip()
    except Exception as e:
        print(f"Image OCR failed: {e}")
        return ""

def get_text(file_path, original_filename):
    """Determine file type and extract text."""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext == '.pdf':
        # First try direct text extraction
        with open(file_path, 'rb') as f:
            text = extract_text_from_pdf(f)
        if not text or len(text) < 10:   # if PDF is image‑based, try OCR
            text = ocr_pdf(file_path)
        return text
    elif ext in ('.png', '.jpg', '.jpeg', '.tiff', '.bmp'):
        return ocr_image(file_path)
    else:
        # Unsupported – treat as empty
        return ""

# ------------------------------------------------------------------
#  FIELD PARSER (same logic as frontend)
# ------------------------------------------------------------------
def parse_ocr_text(text):
    fields = {
        "documentNo": "",
        "pageNo": "",
        "bookNo": "",
        "series": "",
        "date": "",
        "documentType": "",
        "clientName": "",
        "clientAddress": "",
        "competentEvidenceId": "",
        "ctcNumber": "",
        "ctcDate": "",
        "ctcPlaceIssued": "",
        "notes": ""
    }
    if not text:
        return fields

    lines = text.split('\n')
    def find_after(keywords):
        for i, line in enumerate(lines):
            line_lower = line.lower()
            for kw in keywords:
                if kw in line_lower:
                    # remove keyword and colon
                    remainder = line_lower.split(kw, 1)[1].lstrip(": ").strip()
                    if remainder:
                        return remainder
                    # try next line
                    if i + 1 < len(lines):
                        return lines[i+1].strip()
        return "N/A"

    fields["documentNo"] = find_after(["document no.","document number","doc no"])
    fields["pageNo"] = find_after(["page no.","page number"])
    fields["bookNo"] = find_after(["book no.","book number"])
    fields["series"] = find_after(["series","year"])
    fields["date"] = find_after(["date"])
    fields["documentType"] = find_after(["type of document","document type","type"])
    fields["clientName"] = find_after(["client name","name of client"])
    fields["clientAddress"] = find_after(["address","client address"])
    fields["competentEvidenceId"] = find_after(["competent evidence","evidence of identity","id presented"])
    fields["ctcNumber"] = find_after(["ctc no.","ctc number"])
    fields["ctcDate"] = find_after(["ctc date","date of ctc"])
    fields["ctcPlaceIssued"] = find_after(["place issued","ctc place"])
    fields["notes"] = find_after(["notes","remarks"])
    return fields

# ------------------------------------------------------------------
#  CLOUDINARY UPLOAD
# ------------------------------------------------------------------
def upload_to_cloudinary(file_path, original_filename):
    """Upload the file to Cloudinary and return secure_url + public_id."""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                CLOUDINARY_URL,
                files={"file": (original_filename, f)},
                data={"upload_preset": UPLOAD_PRESET}
            )
        result = response.json()
        if response.status_code != 200:
            return None, result.get("error", {}).get("message", "Cloudinary error")
        return result["secure_url"], result["public_id"]
    except Exception as e:
        return None, str(e)

# ------------------------------------------------------------------
#  FLASK APP
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/extract', methods=['POST'])
def extract():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    # Save to a temp file
    suffix = os.path.splitext(secure_filename(file.filename))[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # Extract text
    raw_text = get_text(tmp_path, file.filename)
    print(f"Extracted text length: {len(raw_text)}")

    # Parse fields
    fields = parse_ocr_text(raw_text)

    # Upload to Cloudinary for storage
    url, public_id = upload_to_cloudinary(tmp_path, file.filename)

    # Clean up temp file
    os.unlink(tmp_path)

    return jsonify({
        "fields": fields,
        "url": url,
        "public_id": public_id,
        "error": None if url else "Cloudinary upload failed",
    })

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
