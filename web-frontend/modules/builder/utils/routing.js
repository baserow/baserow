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

/**
 * Removes the runtime-configured preview prefix from a catch-all route path.
 * Nuxt routes are compiled while official images are built, so the preview
 * route itself cannot depend on configuration supplied when the image starts.
 */
export const stripBuilderPreviewPathPrefix = (path, previewPathPrefix) => {
  const normalizedPrefix = (previewPathPrefix || '')
    .split('/')
    .filter(Boolean)
    .join('/')

  if (!normalizedPrefix) {
    return path
  }
  if (path === normalizedPrefix) {
    return ''
  }
  if (path.startsWith(`${normalizedPrefix}/`)) {
    return path.slice(normalizedPrefix.length + 1)
  }
  return path
}
