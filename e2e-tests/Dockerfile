FROM node:24-bookworm as base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgtk-3-0 \
    libasound2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxtst6 \
    libatk1.0-0 \
    libdbus-glib-1-2 \
    libdbus-1-3 \
    libnspr4 \
    libdrm2 \
    libgbm1 \
    libx11-xcb1 \
    libxcursor1 \
    libxi6 \
    libnss3 \
    && apt-get autoclean \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*


COPY --chown=node:node package.json yarn.lock wait-for-services.sh /baserow/e2e-tests/
USER node

WORKDIR /baserow/e2e-tests

RUN yarn install && yarn playwright install && yarn cache clean && chmod +x wait-for-services.sh

CMD ["bash -c './wait-for-services.sh && yarn run test'"]
