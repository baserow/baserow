import { match } from 'path-to-regexp'

export const resolveApplicationRoute = (pages, fullPath) => {
  if (fullPath === undefined || fullPath === null) {
    return undefined
  }
  // Nuxt route.fullPath usually includes query/hash; path-to-regexp matches pathnames.
  const pathname = fullPath.split('?')[0].split('#')[0]

  for (const page of pages) {
    const matcher = match(page.path.slice(1))
    const matched = matcher(pathname)

    if (matched) {
      // matched = { path, params, index? }
      return [page, matched.path, matched.params]
    }
  }

  return undefined
}
