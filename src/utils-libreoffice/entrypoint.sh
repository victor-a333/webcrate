#!/bin/bash
# Start LibreOffice in background
#libreoffice --headless --accept="socket,host=localhost,port=2002;urp;" --nologo --nofirststartwizard &

# Start Flask API (foreground)
exec python3 /app/app.py
