import { match } from 'path-to-regexp'

export const resolveApplicationRoute = (pages, fullPath) => {
  if (fullPath === undefined || fullPath === null) {
    return undefined
  }

  for (const page of pages) {
    const matcher = match(page.path.slice(1))
    const matched = matcher(fullPath)

    if (matched) {
      // matched = { path, params, index? }
      return [page, matched.path, matched.params]
    }
  }

  return undefined
}
