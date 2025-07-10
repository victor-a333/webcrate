from flask import Flask, request, send_file
import os
import subprocess
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = "/tmp"

@app.route('/docx2pdf', methods=['POST'])
def convert():
    file = request.files.get('file')
    if not file:
        return "No file uploaded", 400

    input_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.docx")
    output_path = input_path.replace('.docx', '.pdf')
    file.save(input_path)

    try:
        subprocess.run([
            "libreoffice7.3", "--headless",
            "--convert-to", "pdf",
            input_path,
            "--outdir", UPLOAD_FOLDER
        ], check=True)

        return send_file(output_path, mimetype="application/pdf")

    except subprocess.CalledProcessError as e:
        return f"Conversion failed: {e}", 500
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

app.run(host="0.0.0.0", port=3000)
