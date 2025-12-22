# This a dev image for testing your plugin when installed into the Baserow web-frontend image
FROM baserow/web-frontend:2.0.6 as base
FROM baserow/web-frontend:2.0.6

USER root

ARG PLUGIN_BUILD_UID
ENV PLUGIN_BUILD_UID=${PLUGIN_BUILD_UID:-9999}
ARG PLUGIN_BUILD_GID
ENV PLUGIN_BUILD_GID=${PLUGIN_BUILD_GID:-9999}

# If we aren't building as the same user that owns all the files in the base
# image/installed plugins we need to chown everything first.
COPY --from=base --chown=$PLUGIN_BUILD_UID:$PLUGIN_BUILD_GID /baserow /baserow
RUN groupmod -g $PLUGIN_BUILD_GID node && usermod -u $PLUGIN_BUILD_UID $DOCKER_USER

COPY --chown=$PLUGIN_BUILD_UID:$PLUGIN_BUILD_GID ./plugins/{{ cookiecutter.project_module }}/ $BASEROW_PLUGIN_DIR/{{ cookiecutter.project_module }}/
RUN /baserow/plugins/install_plugin.sh --folder $BASEROW_PLUGIN_DIR/{{ cookiecutter.project_module }} --dev

USER $PLUGIN_BUILD_UID:$PLUGIN_BUILD_GID
CMD ["nuxt-dev"]
