# Installing Baserow with Traefik

If you are using [Traefik](https://doc.traefik.io/traefik/) the example below will show
you how to configure Baserow to work with Traefik.

## Example Traefik compose file

See below for an example docker-compose file that will enable Baserow with Traefik.

```
services:
  baserow:
    image: baserow/baserow:2.0.6
    container_name: baserow
    labels:
        # Explicitly tell Traefik to expose this container
        - "traefik.enable=true"
        # The domain the service will respond to
        - "traefik.http.routers.baserow.rule=Host(`domain.com`)"
    environment:
      - BASEROW_PUBLIC_URL=https://domain.com
    volumes:
      - baserow_data:/baserow/data
volumes:
  baserow_data:
```
