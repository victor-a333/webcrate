# Build frontend assets separately so Node.js and node_modules stay out of runtime.
FROM archlinux:latest AS frontend
RUN pacman --needed --noconfirm -Syu && \
    pacman --needed --noconfirm -S npm && \
    pacman --noconfirm -Scc
WORKDIR /app/assets/admin
COPY app/assets/admin/package*.json ./
RUN npm install --verbose
COPY app/assets/admin/ ./
RUN NODE_OPTIONS=--openssl-legacy-provider npm run build

# Arch bundles the Docker client and engine; retain only the client at runtime.
FROM archlinux:latest AS docker-cli
RUN pacman --needed --noconfirm -Syu && \
    pacman --needed --noconfirm -S docker

FROM archlinux:latest

#update pacman db
RUN pacman --needed --noconfirm -Syu && \
    pacman --needed --noconfirm -S binutils git composer nano openssh unzip mariadb-clients iputils inetutils which python-yaml python-munch python-setuptools nginx \
    php php-fpm php-intl php-sqlite php-gd php-xsl php-tidy php-imagick php-memcached php-igbinary debugedit && \
    pacman -U --noconfirm https://archive.archlinux.org/packages/f/fakeroot/fakeroot-1.34-1-x86_64.pkg.tar.zst && \
    pacman --noconfirm -Scc

COPY --from=docker-cli /usr/bin/docker /usr/bin/docker
# Verify that the copied client runs with the runtime libraries.
RUN docker --version

#make automake bison binutils autoconf gcc patch
RUN pacman --needed --noconfirm -S sudo && pacman --noconfirm -Scc
RUN useradd -m -s /bin/bash dev
RUN useradd -m -s /bin/bash app
RUN usermod -p "dev" dev
RUN usermod -u 555 dev
RUN groupmod -g 555 dev
RUN echo 'dev ALL=(ALL) NOPASSWD: ALL' | EDITOR='tee -a' visudo
RUN sed -i "s/#MAKEFLAGS=\"-j2\"/MAKEFLAGS=\"-j12\"/g" /etc/makepkg.conf

USER dev
WORKDIR /home/dev

#install symfony-cli-bin
RUN git clone https://aur.archlinux.org/symfony-cli-bin.git && \
    cd symfony-cli-bin && \
    makepkg -scir --nocheck --noconfirm --skipchecksums && \
    rm -rf /home/dev/symfony-cli-bin && \
    sudo pacman --noconfirm -Scc

#install docker-systemctl-replacement-git
RUN git clone https://aur.archlinux.org/docker-systemctl-replacement-git.git && \
    cd docker-systemctl-replacement-git && \
    makepkg -scir --nocheck --noconfirm --skipchecksums && \
    rm -rf /home/dev/docker-systemctl-replacement-git && \
    sudo pacman --noconfirm -Scc

USER root

RUN chown root:root /bin/systemctl.py && \
    chmod a+x /bin/systemctl.py && \
    mv /bin/systemctl /bin/systemctl_original && \
    cp /bin/systemctl.py /bin/systemctl && \
    systemctl enable php-fpm && \
    systemctl enable nginx && \
    sed -i "s/.*open_basedir =.*/open_basedir =/g" /etc/php/php.ini && \
    sed -i "s/; extension = imagick/extension=imagick/g" /etc/php/conf.d/imagick.ini;
COPY pool.conf /etc/php/php-fpm.d/pool.conf
COPY php.ini /etc/php/conf.d/user.ini
RUN echo 'app ALL=(ALL) NOPASSWD: /webcrate/versions.py' | EDITOR='tee -a' visudo && \
    echo 'app ALL=(ALL) NOPASSWD: /webcrate/updateprojects.py' | EDITOR='tee -a' visudo && \
    echo 'app ALL=(ALL) NOPASSWD: /webcrate/updateredirects.py' | EDITOR='tee -a' visudo && \
    echo 'app ALL=(ALL) NOPASSWD: /webcrate/reload-redirect.py' | EDITOR='tee -a' visudo && \
    echo 'app ALL=(ALL) NOPASSWD: /webcrate/reload.py' | EDITOR='tee -a' visudo
COPY --chown=app:app app /app
COPY --from=frontend --chown=app:app /app/public/build/ /app/public/build/
RUN mkdir /webcrate && \
    chown app:app /webcrate
WORKDIR /app
USER app
RUN composer config --no-plugins allow-plugins.symfony/flex true && \
    sed -i "s/.*\"@auto-scripts\".*/ /g" composer.json && \
    rm -f composer.lock && \
    composer install --no-scripts && \
    composer clear-cache
WORKDIR /app/assets/admin
USER root
COPY ["init-db.py", "log.py", "updateprojects.py", "updateredirects.py", "reload-redirect.py", "versions.py", "reload.py", "/webcrate"]
COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh
CMD ["/entrypoint.sh"]
RUN chmod u+x /webcrate/init-db.py && \
    chmod a+rxs /webcrate/log.py && \
    chmod a+rxs /webcrate/versions.py && \
    chmod a+rxs /webcrate/updateprojects.py && \
    chmod a+rxs /webcrate/updateredirects.py && \
    chmod a+rxs /webcrate/reload.py && \
    chmod a+rxs /webcrate/reload-redirect.py && \
    chmod u+x /entrypoint.sh
EXPOSE 80