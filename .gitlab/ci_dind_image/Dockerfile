FROM docker:20.10.18-dind AS upstream

# copy everything to a clean image, so we can change the exposed ports
# see https://gitlab.com/search?search=Service+docker+dind+probably+didn%27t+start+properly&nav_source=navbar&project_id=250833&group_id=9970&scope=issues&sort=updated_desc
FROM scratch

COPY --from=upstream / /

VOLUME /var/lib/docker

#EXPOSE 2375/tcp # is for insecure connections, and having both breaks Gitlab's "wait-for-it" service
EXPOSE 2376/tcp

ENTRYPOINT ["dockerd-entrypoint.sh"]
CMD []

ENV DOCKER_VERSION=20.10.18
ENV DOCKER_TLS_CERTDIR='/certs'
