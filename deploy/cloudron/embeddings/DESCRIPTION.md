```
cloudron install -l embeddings.{YOUR_DOMAIN} --image baserow/embeddings:1.0.0
```

In the Baserow app in Cloudron do:

```
cloudron env set BASEROW_EMBEDDINGS_API_URL=https://embeddings.{YOUR_DOMAIN}
```
