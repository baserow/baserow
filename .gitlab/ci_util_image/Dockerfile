# A small helper image which has some useful tools pre-installed that are used by ci
# stages. By building our own little image it means every single ci job doesn't need
# to repeatedly re-install these tools when they run.
FROM docker:28-rc

# Install Node.js directly in Alpine
RUN apk add --no-cache nodejs npm

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache curl git jq python3 py3-pip openssh-client nodejs yarn docker-cli-compose bash && ln -sf python3 /usr/bin/python
RUN mkdir /baserow && python3 -m venv /baserow/venv && . /baserow/venv/bin/activate && pip3 install coverage
