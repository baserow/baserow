/**
 * Environment variable remapping for Nuxt 3 runtime config.
 * Remaps legacy env vars to NUXT_ prefixed vars for runtime config support.
 *
 * This allows existing environment variable names (e.g., PUBLIC_BACKEND_URL)
 * to work with Nuxt 3's runtime config system, which expects NUXT_PUBLIC_*
 * prefixed variables for runtime overrides.
 *
 * Import this file before starting Nuxt (dev or prod).
 */

// Mapping: legacy env var -> NUXT runtime config env var
const envMapping = {
  // Private config (server-only)
  PRIVATE_BACKEND_URL: 'NUXT_PRIVATE_BACKEND_URL',

  // Public config (available on client via SSR)
  PUBLIC_BACKEND_URL: 'NUXT_PUBLIC_PUBLIC_BACKEND_URL',
  PUBLIC_WEB_FRONTEND_URL: 'NUXT_PUBLIC_PUBLIC_WEB_FRONTEND_URL',
  DOWNLOAD_FILE_VIA_XHR: 'NUXT_PUBLIC_DOWNLOAD_FILE_VIA_XHR',
  BASEROW_DISABLE_PUBLIC_URL_CHECK:
    'NUXT_PUBLIC_BASEROW_DISABLE_PUBLIC_URL_CHECK',
  INITIAL_TABLE_DATA_LIMIT: 'NUXT_PUBLIC_INITIAL_TABLE_DATA_LIMIT',
  HOURS_UNTIL_TRASH_PERMANENTLY_DELETED:
    'NUXT_PUBLIC_HOURS_UNTIL_TRASH_PERMANENTLY_DELETED',
  DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS:
    'NUXT_PUBLIC_DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS',
  BASEROW_MAX_IMPORT_FILE_SIZE_MB:
    'NUXT_PUBLIC_BASEROW_MAX_IMPORT_FILE_SIZE_MB',
  FEATURE_FLAGS: 'NUXT_PUBLIC_FEATURE_FLAGS',
  BASEROW_DISABLE_GOOGLE_DOCS_FILE_PREVIEW:
    'NUXT_PUBLIC_BASEROW_DISABLE_GOOGLE_DOCS_FILE_PREVIEW',
  BASEROW_MAX_SNAPSHOTS_PER_GROUP:
    'NUXT_PUBLIC_BASEROW_MAX_SNAPSHOTS_PER_GROUP',
  BASEROW_FRONTEND_SAME_SITE_COOKIE:
    'NUXT_PUBLIC_BASEROW_FRONTEND_SAME_SITE_COOKIE',
  BASEROW_FRONTEND_JOBS_POLLING_TIMEOUT_MS:
    'NUXT_PUBLIC_BASEROW_FRONTEND_JOBS_POLLING_TIMEOUT_MS',
  POSTHOG_PROJECT_API_KEY: 'NUXT_PUBLIC_POSTHOG_PROJECT_API_KEY',
  POSTHOG_HOST: 'NUXT_PUBLIC_POSTHOG_HOST',
  BASEROW_USE_PG_FULLTEXT_SEARCH: 'NUXT_PUBLIC_BASEROW_USE_PG_FULLTEXT_SEARCH',
  BASEROW_INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT:
    'NUXT_PUBLIC_INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT',
  BASEROW_ROW_PAGE_SIZE_LIMIT: 'NUXT_PUBLIC_BASEROW_ROW_PAGE_SIZE_LIMIT',
  BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT:
    'NUXT_PUBLIC_BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT',
  BASEROW_DISABLE_SUPPORT: 'NUXT_PUBLIC_BASEROW_DISABLE_SUPPORT',
  BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN:
    'NUXT_PUBLIC_BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN',
  // TODO find a way to load these vars from private folders
  BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES:
    'NUXT_PUBLIC_BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES',
  BASEROW_PRICING_URL: 'NUXT_PUBLIC_BASEROW_PRICING_URL',
  BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL:
    'NUXT_PUBLIC_BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL',
  SENTRY_DSN: 'NUXT_PUBLIC_SENTRY_DSN',
  SENTRY_ENVIRONMENT: 'NUXT_PUBLIC_SENTRY_ENVIRONMENT',
  MEDIA_URL: 'NUXT_PUBLIC_MEDIA_URL',
}

// Remap env vars: only if legacy var exists AND NUXT_ var is not already set
for (const [legacyKey, nuxtKey] of Object.entries(envMapping)) {
  if (
    process.env[legacyKey] !== undefined &&
    process.env[nuxtKey] === undefined
  ) {
    process.env[nuxtKey] = process.env[legacyKey]
  }
}

// Handle BASEROW_PUBLIC_URL convenience variable (sets both backend and frontend URLs)
if (process.env.BASEROW_PUBLIC_URL) {
  if (!process.env.NUXT_PUBLIC_PUBLIC_BACKEND_URL) {
    process.env.NUXT_PUBLIC_PUBLIC_BACKEND_URL = process.env.BASEROW_PUBLIC_URL
  }
  if (!process.env.NUXT_PUBLIC_PUBLIC_WEB_FRONTEND_URL) {
    process.env.NUXT_PUBLIC_PUBLIC_WEB_FRONTEND_URL =
      process.env.BASEROW_PUBLIC_URL
  }
}

// Handle BASEROW_EMBEDDED_SHARE_URL fallback to PUBLIC_WEB_FRONTEND_URL
if (!process.env.NUXT_PUBLIC_BASEROW_EMBEDDED_SHARE_URL) {
  if (process.env.BASEROW_EMBEDDED_SHARE_URL) {
    process.env.NUXT_PUBLIC_BASEROW_EMBEDDED_SHARE_URL =
      process.env.BASEROW_EMBEDDED_SHARE_URL
  } else if (process.env.NUXT_PUBLIC_PUBLIC_WEB_FRONTEND_URL) {
    // Use the already-remapped variable (PUBLIC_WEB_FRONTEND_URL -> NUXT_PUBLIC_PUBLIC_WEB_FRONTEND_URL)
    process.env.NUXT_PUBLIC_BASEROW_EMBEDDED_SHARE_URL =
      process.env.NUXT_PUBLIC_PUBLIC_WEB_FRONTEND_URL
  }
}

// Handle BASEROW_EXTRA_PUBLIC_URLS with hostname extraction transformation
if (
  process.env.BASEROW_EXTRA_PUBLIC_URLS &&
  !process.env.NUXT_PUBLIC_EXTRA_PUBLIC_WEB_FRONTEND_HOSTNAMES
) {
  // Inline parseHostnamesFromUrls to avoid importing from source files
  // (source files are not copied to production Docker images)
  const hostnames = process.env.BASEROW_EXTRA_PUBLIC_URLS.split(',')
    .map((url) => url.trim())
    .filter((url) => url !== '')
    .map((url) => {
      try {
        return new URL(url).hostname
      } catch (e) {
        console.warn(`Invalid URL in BASEROW_EXTRA_PUBLIC_URLS: ${url}`)
        return null
      }
    })
    .filter((hostname) => hostname !== null)
  process.env.NUXT_PUBLIC_EXTRA_PUBLIC_WEB_FRONTEND_HOSTNAMES =
    JSON.stringify(hostnames)
}

// Handle BASEROW_BUILDER_DOMAINS with comma-split transformation
if (
  process.env.BASEROW_BUILDER_DOMAINS &&
  !process.env.NUXT_PUBLIC_BASEROW_BUILDER_DOMAINS
) {
  const domains = process.env.BASEROW_BUILDER_DOMAINS.split(',')
    .map((d) => d.trim())
    .filter((d) => d !== '')
  process.env.NUXT_PUBLIC_BASEROW_BUILDER_DOMAINS = JSON.stringify(domains)
}
