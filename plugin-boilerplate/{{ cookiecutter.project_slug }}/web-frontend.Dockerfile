FROM baserow/web-frontend:1.30.1

USER root

COPY ./plugins/{{ cookiecutter.project_module }}/ /baserow/plugins/{{ cookiecutter.project_module }}/
RUN /baserow/plugins/install_plugin.sh --folder /baserow/plugins/{{ cookiecutter.project_module }}

USER $UID:$GID
