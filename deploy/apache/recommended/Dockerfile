FROM debian:bookworm-slim
#Don't ask questions during install
ENV DEBIAN_FRONTEND=noninteractive

#Install apache2 and enable proxy mode
RUN apt-get update \
    && apt-get -y install apache2 \
    && a2enmod proxy headers proxy_http proxy_wstunnel rewrite \
    && apt-get autoclean \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

COPY sub-domain.conf /etc/apache2/sites-available/sub-domain.conf

RUN a2dissite 000-default.conf && a2ensite sub-domain.conf \
    && apachectl configtest && apache2ctl -t && apache2ctl -S

CMD ["apachectl", "-D", "FOREGROUND"]
