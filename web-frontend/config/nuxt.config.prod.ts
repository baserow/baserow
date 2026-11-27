/**
 * Production Nuxt configuration
 *
 * We use a direct import rather than `extends: ['./nuxt.config.base.ts']` because
 * Nuxt 3's `extends` mechanism is designed for Nuxt layers (directories containing
 * their own nuxt.config.ts, app.vue, pages/, etc.), not for importing individual
 * config files directly.
 *
 * When pointing `extends` to a .ts file, Nuxt shows:
 *   "WARN Cannot extend config from ./nuxt.config.base.ts"
 *
 * By using a standard ES module import/export, we achieve the same result reliably.
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { parseEnv } from 'node:util'
import baseConfig from './nuxt.config.base.ts'

// Server source maps are only used when Sentry uploads them: the server doesn't
// run with source map support. Building them takes the heap the build needs
// from under 4 GB to over 6 GB, so they're only built when Sentry's bundler
// plugin will upload them. It reads `.env.sentry-build-plugin` after this
// config is evaluated, and uploads only with a token, a project, and an org
// (or an org-scoped `sntrys_` token). Client maps stay, because the browser
// and a Sentry that reads them from the public files both use them.
function sentryWillUploadSourceMaps() {
  let env = process.env
  try {
    const file = join(process.cwd(), '.env.sentry-build-plugin')
    env = {
      ...env,
      ...parseEnv(readFileSync(file, 'utf-8').replace(/^\uFEFF/, '')),
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error
  }
  const token = env.SENTRY_AUTH_TOKEN?.trim()
  const org = env.SENTRY_ORG?.trim()
  const project = env.SENTRY_PROJECT?.split(',')[0].trim()
  return Boolean(token && project && (org || token.startsWith('sntrys_')))
}

const uploadsSourceMaps = sentryWillUploadSourceMaps()

export default {
  ...baseConfig,
  nitro: {
    ...baseConfig.nitro,
    // Precompress the static assets at build time, so that they're served with
    // brotli or gzip even when no compressing reverse proxy is in front.
    compressPublicAssets: { gzip: true, brotli: true },
  },
  sourcemap: {
    server: uploadsSourceMaps,
    client: true,
  },
}
