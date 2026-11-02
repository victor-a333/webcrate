# Build frontend assets separately so Node.js and node_modules stay out of runtime.
FROM node:22-trixie-slim AS frontend
WORKDIR /app/assets/admin
COPY app/assets/admin/package*.json ./
RUN npm install --verbose
COPY app/assets/admin/ ./
RUN NODE_OPTIONS=--openssl-legacy-provider npm run build

# Only the client binary is needed to control the host's Docker daemon.
FROM docker:29-cli AS docker-cli

FROM debian:trixie-slim

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates tzdata composer git nano openssh-client unzip mariadb-client \
        iputils-ping inetutils-telnet debianutils python3 python3-yaml python3-munch \
        nginx supervisor sudo \
        php8.4-cli php8.4-fpm php8.4-curl php8.4-mbstring php8.4-xml \
        php8.4-intl php8.4-sqlite3 php8.4-mysql php8.4-gd php8.4-tidy \
        php8.4-imagick php8.4-memcached php8.4-igbinary php8.4-soap php8.4-zip && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -U -s /bin/bash app && \
    rm /etc/php/8.4/fpm/pool.d/www.conf && \
    mkdir -p /run/php /webcrate && \
    chown app:app /webcrate

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
RUN docker --version && composer --version

COPY pool.conf /etc/php/8.4/fpm/pool.d/pool.conf
COPY php.ini /etc/php/8.4/mods-available/webcrate.ini
RUN phpenmod webcrate && \
    printf '%s\n' \
        'app ALL=(ALL) NOPASSWD: /webcrate/versions.py' \
        'app ALL=(ALL) NOPASSWD: /webcrate/updateprojects.py' \
        'app ALL=(ALL) NOPASSWD: /webcrate/updateredirects.py' \
        'app ALL=(ALL) NOPASSWD: /webcrate/reload-redirect.py' \
        'app ALL=(ALL) NOPASSWD: /webcrate/reload.py' \
        > /etc/sudoers.d/webcrate && \
    chmod 0440 /etc/sudoers.d/webcrate && \
    visudo -cf /etc/sudoers.d/webcrate

COPY --chown=app:app app /app
COPY --from=frontend --chown=app:app /app/public/build/ /app/public/build/
WORKDIR /app
USER app
# Keep dev dependencies: init-db.py loads Doctrine fixtures in the dev environment.
# The checked-in lock still targets Symfony 5.1; retain the existing resolution behavior.
RUN composer config --no-plugins allow-plugins.symfony/flex true && \
    sed -i 's/.*"@auto-scripts".*/ /g' composer.json && \
    rm -f composer.lock && \
    composer install --no-scripts --no-interaction --prefer-dist && \
    composer clear-cache

USER root
COPY ["init-db.py", "log.py", "updateprojects.py", "updateredirects.py", "reload-redirect.py", "versions.py", "reload.py", "/webcrate/"]
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
# Normalize scripts copied from Windows checkouts before executing them on Linux.
RUN mkdir -p /app/var /app/logs && \
    chown -R app:app /app/var /app/logs && \
    sed -i 's/\r$//' /entrypoint.sh /webcrate/*.py && \
    chmod 0755 /entrypoint.sh /webcrate/*.py && \
    php-fpm8.4 -t && nginx -t

EXPOSE 80
CMD ["/entrypoint.sh"]
