FROM openjdk:17.0.2

ARG UID
ENV UID=${UID:-1000}
ARG GID
ENV GID=${GID:-1000}

# We might be running as a user which already exists in this image. In that situation
# Everything is OK and we should just continue on.
RUN groupadd -g $GID baserow_docker_group || exit 0
RUN useradd -l --shell /bin/bash -u $UID -g $GID -o -c "" -m baserow_docker_user || exit 0

RUN mkdir -p /workspace/src && chown -R $UID:$GID /workspace

USER $UID:$GID
WORKDIR /workspace

ENV ANTLR_VERSION=4.9
ENV CLASSPATH=.:/workspace/antlr-${ANTLR_VERSION}-complete.jar:$CLASSPATH

RUN curl -O https://www.antlr.org/download/antlr-${ANTLR_VERSION}-complete.jar \
    && mv antlr-${ANTLR_VERSION}-complete.jar antlr.jar \
    && chmod +x antlr.jar
