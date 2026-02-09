# Setup embeddings server in dev environment

If you would like to use the AI-assistant in combination with the search documentation
tool, then you must start the embeddings server.

## Getting Started

You can build and start the embedding service by adding `ai` to the `COMPOSE_PROFILES` environment variable:

```bash
COMPOSE_PROFILES=ai
```

If you need both `ai` and `optional` profiles, combine them with a comma:

```bash
COMPOSE_PROFILES=ai,optional
```

After starting the services, make sure the correct environment variables are set. In particular, `BASEROW_EMBEDDINGS_API_URL` must be set correctly for the embedding server to work. See [ai-assistant.md](../installation/ai-assistant.md) for the full list of required variables.

Then, run the management command to schedule the initial import:

From the host:

```bash
just dcd run --rm backend manage sync_knowledge_base
```

From inside the container:
```bash
./baserow sync_knowledge_base
```

This will schedule a task to import `website_export.csv` containing all the docs and generate the embeddings using the local service. Once completed, asking the assistant to search for docs should show "Exploring the knowledge base..." in the UI when the assistant uses the `search_docs` tool, and the answers should show sources from the docs.


## Troubleshooting

### Kuma is not available in the sidebar

Make sure `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` is set correctly both in the backend and in the frontend. See [ai-assistant.md](../installation/ai-assistant.md) for more information.

### Kuma is visible but it doesn't search the docs

Run the management command to synchronize the docs in the knowledge base:

From the host:
```bash
just dcd run --rm backend manage sync_knowledge_base
```

From inside the container:
```bash
./baserow sync_knowledge_base
```


### The embedding service is not reachable

Verify the server is up and running by executing one of the following commands:

From the host:
```bash
curl -X POST "http://localhost:7999/embed" \
  -H "Content-Type: application/json" \
  -d '{"texts": "test"}'
```

From inside the container:

```bash
curl -X POST "$BASEROW_EMBEDDINGS_API_URL/embed" \
  -H "Content-Type: application/json" \
  -d '{"texts": "test"}'
```

This command should return a vector of more than 500 numbers. If it doesn't, check that the embeddings container is running and healthy.