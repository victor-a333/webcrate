FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    wget tar gnupg curl \
    python3 python3-pip \
#    unoconv \
    libxinerama1 libxrender1 libxrandr2 libxcb1 libx11-xcb1 \
    libglu1-mesa libsm6 libnss3 libdbus-1-3 libcups2 libcairo2 libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Flask for API
RUN pip3 install --break-system-packages flask
#RUN apt-get install -y python3-flask

# Install LibreOffice 7.3.7.2 manually
RUN wget https://downloadarchive.documentfoundation.org/libreoffice/old/7.3.7.2/deb/x86_64/LibreOffice_7.3.7.2_Linux_x86-64_deb.tar.gz && \
    tar -xzf LibreOffice_7.3.7.2_Linux_x86-64_deb.tar.gz && \
    dpkg -i LibreOffice_7.3.7.2_Linux_x86-64_deb/DEBS/*.deb && \
    rm -rf LibreOffice_7.3.7.2_Linux_x86-64_deb*

# Copy API server
COPY app.py /app/app.py
COPY ["entrypoint.sh", "/"]
RUN chmod u+x /entrypoint.sh
WORKDIR /app

EXPOSE 3000

CMD ["/entrypoint.sh"]