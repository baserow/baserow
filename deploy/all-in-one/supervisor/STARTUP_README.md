Welcome to Baserow. See https://baserow.io/docs/installation%2Finstall-with-docker for detailed instructions on
how to use this Docker image.

IMPORTANT: Data Volume Safety
- Never run multiple Baserow containers on the same data volume simultaneously.
  Doing so will corrupt your PostgreSQL database.
- Always stop and remove old containers before starting new ones:
    docker stop baserow && docker rm baserow
- Always use `docker stop` (not `docker kill`) to allow a clean shutdown.
- If PostgreSQL fails to start after an unclean shutdown, set
  BASEROW_ALLOW_PG_RECOVERY=yes to allow automatic crash recovery.
