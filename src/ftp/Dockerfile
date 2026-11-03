FROM debian:trixie-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        proftpd-core proftpd-mod-crypto openssl python3 python3-yaml && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /webcrate/tls /run/proftpd && \
    touch /etc/ftp.passwd && chmod 600 /etc/ftp.passwd

WORKDIR /
COPY proftpd.conf /etc/proftpd/proftpd.conf
COPY parse-projects.py /webcrate/parse-projects.py
COPY entrypoint.sh /
RUN sed -i 's/\r$//' /entrypoint.sh /webcrate/parse-projects.py && \
    chmod 755 /webcrate/parse-projects.py /entrypoint.sh
EXPOSE 21
CMD ["/entrypoint.sh"]
