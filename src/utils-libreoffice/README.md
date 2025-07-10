# LibreOffice DOCX to PDF Converter (Docker + Flask)

This project provides a simple HTTP API that converts `.docx` files to `.pdf` using LibreOffice in a single Docker container. It's based on `debian:bookworm-slim`, with LibreOffice 7.3.7 installed and a lightweight Flask server for conversion requests.

---

## 🚀 Features

- Converts `.docx` → `.pdf` using LibreOffice CLI
- Simple Flask-based HTTP API
- Clean, stateless Docker container
- No socket or `unoconv` needed

---

