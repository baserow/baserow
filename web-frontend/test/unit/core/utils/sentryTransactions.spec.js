import { describe, expect, test } from 'vitest'

import { dropRouteParams } from '@baserow/modules/core/utils/sentryTransactions'

const TOKEN = 'a'.repeat(64)

describe('dropRouteParams', () => {
  test('drops the params of the route from a navigation transaction', () => {
    const event = dropRouteParams({
      type: 'transaction',
      transaction: '/password-reset/:token',
      contexts: {
        trace: {
          op: 'navigation',
          data: {
            'sentry.op': 'navigation',
            'url.template': '/password-reset/:token',
            'url.path.parameter.token': TOKEN,
            'params.token': TOKEN,
            'query.next': '/dashboard',
          },
        },
      },
      spans: [{ op: 'ui.vue.mount', data: { 'params.token': TOKEN, a: 1 } }],
    })

    expect(event.contexts.trace.data).toStrictEqual({
      'sentry.op': 'navigation',
      'url.template': '/password-reset/:token',
      'query.next': '/dashboard',
    })
    expect(event.spans).toStrictEqual([{ op: 'ui.vue.mount', data: { a: 1 } }])
  })
})
