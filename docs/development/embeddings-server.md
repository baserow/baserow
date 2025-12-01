# Setup embeddings server in dev environment

If you would like to use the AI-assistant in combination with the search documentation
tool, then you must add the embeddings server. This 

## Docker compose

Add the following to your `docker-compose.dev.yml` and then (re)start your dev server.
The `BASEROW_EMBEDDINGS_API_URL=http://embeddings:80` variable is already configured by
default for the backend container, so it should then work out of the box.

```yaml
  embeddings:
    build:
      context: ./embeddings
      dockerfile: Dockerfile
    ports:
      - "${HOST_PUBLISH_IP:-127.0.0.1}:7999:80"
    networks:
      local:
    restart: unless-stopped
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import requests; requests.get('http://localhost/health').raise_for_status()",
        ]
      interval: 1m30s
      timeout: 10s
      retries: 3
```
