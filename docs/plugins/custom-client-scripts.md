# Custom Client Scripts

> **Enterprise feature** -- requires an active enterprise license.

The `BASEROW_EXTRA_CLIENT_SCRIPT_URLS` environment variable lets self-hosted operators
inject custom client-side JavaScript into every page without building a full plugin.
Scripts are loaded in the `<head>` and execute before the application hydrates.

## Configuration

Set the environment variable to one or more comma-separated URLs pointing to your
scripts:

```bash
BASEROW_EXTRA_CLIENT_SCRIPT_URLS=https://example.com/my-script.js
```

Multiple scripts:

```bash
BASEROW_EXTRA_CLIENT_SCRIPT_URLS=https://example.com/analytics.js,https://example.com/banner.js
```

## The `window.__baserow` API

Before your scripts execute, Baserow creates a `window.__baserow` global with the
following properties:

| Property | Description |
|---|---|
| `window.__baserow.config` | The public runtime configuration object (read-only). |
| `window.__baserow.hook(name, fn)` | Register a callback for a Nuxt lifecycle hook. |
| `window.__baserow.$router` | The Vue Router instance (available after the app plugin runs). |

### Registering hooks

Use `window.__baserow.hook()` to run code at specific lifecycle moments. Hooks
registered before the Nuxt app is ready are queued and replayed automatically once the
app finishes loading.

```js
// Log when the application has mounted
window.__baserow.hook('app:mounted', () => {
  console.log('Baserow has mounted')
})
```

```js
// Access runtime config inside a hook
window.__baserow.hook('app:mounted', () => {
  const config = window.__baserow.config
  console.log('Public URL:', config.PUBLIC_WEB_FRONTEND_URL)
})
```

```js
// Use the router to react to navigation
window.__baserow.hook('app:mounted', () => {
  window.__baserow.$router.afterEach((to) => {
    console.log('Navigated to', to.fullPath)
  })
})
```

## Examples

### Inject a third-party analytics snippet

```js
window.__baserow.hook('app:mounted', () => {
  const script = document.createElement('script')
  script.src = 'https://analytics.example.com/tracker.js'
  script.async = true
  document.head.appendChild(script)
})
```

### Show a maintenance banner

```js
window.__baserow.hook('app:mounted', () => {
  const banner = document.createElement('div')
  banner.textContent = 'Scheduled maintenance tonight at 22:00 UTC'
  banner.style.cssText =
    'position:fixed;top:0;left:0;right:0;padding:8px;background:#f59e0b;' +
    'color:#000;text-align:center;z-index:9999;font-size:14px;'
  document.body.prepend(banner)
})
```

### Track page views

```js
window.__baserow.hook('app:mounted', () => {
  const track = (path) => {
    fetch('https://analytics.example.com/collect', {
      method: 'POST',
      body: JSON.stringify({ path, ts: Date.now() }),
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // Initial page
  track(window.location.pathname)

  // Subsequent navigations
  window.__baserow.$router.afterEach((to) => {
    track(to.fullPath)
  })
})
```

## Notes

* Scripts are only loaded when the enterprise license includes the
  `ENTERPRISE_SETTINGS` feature.
* The `hook()` function accepts any
  [Nuxt lifecycle hook name](https://nuxt.com/docs/api/advanced/hooks#app-hooks-runtime).
  `app:mounted` is the most common choice for DOM manipulation.
* Because scripts run in the browser, they cannot access backend secrets or server-side
  configuration.
