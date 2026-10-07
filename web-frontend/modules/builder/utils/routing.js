import { match } from 'path-to-regexp'

export const resolveApplicationRoute = (pages, fullPath) => {
  // Vue Router 5 omits an optional catch-all parameter when it matches the
  // root path. Treat the omitted value as the empty path so the homepage can
  // still be resolved.
  const path = fullPath ?? ''

  for (const page of pages) {
    const matcher = match(page.path.slice(1))
    const matched = matcher(path)

    if (matched) {
      // matched = { path, params, index? }
      return [page, matched.path, matched.params]
    }
  }

  return undefined
}

export const resolveBuilderPagePath = (pathMatch) =>
  Array.isArray(pathMatch) ? pathMatch.join('/') : pathMatch || ''

/** Decodes an internal next destination, rejecting external URLs. */
export const resolveSafeNextPath = (next) => {
  if (typeof next !== 'string') {
    return null
  }

  try {
    const decoded = decodeURIComponent(next)
    const internalOrigin = 'http://builder.internal'
    const resolved = new URL(decoded, internalOrigin)
    if (!decoded.startsWith('/') || resolved.origin !== internalOrigin) {
      return null
    }
    return `${resolved.pathname}${resolved.search}${resolved.hash}`
  } catch {
    return null
  }
}
