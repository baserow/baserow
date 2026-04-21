import { defineEventHandler, setResponseHeader, createError } from 'h3'
import { readFile } from 'node:fs/promises'

export default defineEventHandler(async (event) => {
  const raw = process.env.BASEROW_EXTRA_CLIENT_SCRIPT_PATHS
  const paths = raw
    ? raw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    : []
  if (paths.length === 0) {
    throw createError({ statusCode: 404 })
  }

  let contents
  try {
    contents = await Promise.all(paths.map((p) => readFile(p, 'utf-8')))
  } catch (err) {
    if (
      err &&
      typeof err === 'object' &&
      'code' in err &&
      err.code === 'ENOENT'
    ) {
      throw createError({ statusCode: 404 })
    }
    throw createError({
      statusCode: 500,
      statusMessage: 'Failed to read extra client script',
    })
  }

  setResponseHeader(
    event,
    'Content-Type',
    'application/javascript; charset=utf-8'
  )
  setResponseHeader(event, 'Cache-Control', 'no-cache')
  return contents.join('\n;\n')
})
