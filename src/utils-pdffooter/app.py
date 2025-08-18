from flask import Flask, request, send_file
import os
import subprocess
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = "/tmp"

def sanitize_pdf(input_path: str) -> str:
    cleaned_path = input_path.replace(".pdf", "_cleaned.pdf")
    subprocess.run([
        "gs", "-sDEVICE=pdfwrite", "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sOutputFile=" + cleaned_path,
        input_path
    ], check=True)
    return cleaned_path

@app.route('/add-header', methods=['POST'])
def add_header():
    pdf_file = request.files.get('file')
    header_file = request.files.get('header')

    if not pdf_file or not header_file:
        return "Missing 'file' or 'header' in request", 400

    uid = str(uuid.uuid4())

    input_path = os.path.join(UPLOAD_FOLDER, f"{uid}_input.pdf")
    header_path = os.path.join(UPLOAD_FOLDER, f"{uid}_header.pdf")
    output_path = os.path.join(UPLOAD_FOLDER, f"{uid}_output.pdf")

    pdf_file.save(input_path)
    header_file.save(header_path)

    try:
        cleaned_path = sanitize_pdf(input_path)

        subprocess.run([
            "python3", "/app/add_header_to_pdf.py",
            header_path, cleaned_path, output_path
        ], check=True)

        return send_file(output_path, mimetype="application/pdf")

    except subprocess.CalledProcessError as e:
        return f"Processing failed: {str(e)}", 500

    finally:
        for path in [input_path, header_path, output_path,
                     input_path.replace(".pdf", "_cleaned.pdf")]:
            if os.path.exists(path):
                os.remove(path)

app.run(host="0.0.0.0", port=3000)
