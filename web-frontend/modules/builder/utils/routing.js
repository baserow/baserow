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
