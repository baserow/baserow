import { createTransport } from '@sentry/core'

export function makeFakeTransport(options) {
  return createTransport(options, async () => ({ statusCode: 200 }))
}
