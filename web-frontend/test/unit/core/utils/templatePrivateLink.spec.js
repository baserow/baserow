import { describe, expect, test } from 'vitest'

import {
  addPrivateLinkHeader,
  redactPrivateLinkTokens,
} from '@baserow/modules/core/utils/templatePrivateLink'

const TOKEN = 'a'.repeat(64)

describe('addPrivateLinkHeader', () => {
  test.each([
    ['template-private-link', TOKEN, TOKEN],
    ['template', TOKEN, undefined],
  ])('on %s with %s sends %s', (name, token, expected) => {
    const nuxtApp = {
      $router: { currentRoute: { value: { name, params: { token } } } },
    }

    const config = addPrivateLinkHeader(nuxtApp)({ headers: {} })

    expect(config.headers['Baserow-Template-Authorization']).toBe(expected)
  })

  test('keeps the token of a link opened before', () => {
    const nuxtApp = {
      $router: {
        currentRoute: {
          value: { name: 'template-private-link', params: { token: TOKEN } },
        },
      },
    }
    const before = 'b'.repeat(64)

    const config = addPrivateLinkHeader(nuxtApp)({
      headers: { 'Baserow-Template-Authorization': before },
    })

    expect(config.headers['Baserow-Template-Authorization']).toBe(before)
  })
})

describe('redactPrivateLinkTokens', () => {
  test('replaces the token in the URLs of an event', () => {
    const link = `https://baserow.io/template/crm/private-link/${TOKEN}`
    const login = `https://baserow.io/login?original=%2Ftemplate%2Fcrm%2Fprivate-link%2F${TOKEN}`

    const event = redactPrivateLinkTokens({
      event: '$identify',
      properties: {
        $current_url: link,
        $pathname: '/dashboard',
        list: [login],
      },
      $set_once: { $initial_current_url: login },
    })

    expect(event.properties).toEqual({
      $current_url: 'https://baserow.io/template/crm/private-link/[redacted]',
      $pathname: '/dashboard',
      list: [
        'https://baserow.io/login?original=%2Ftemplate%2Fcrm%2Fprivate-link%2F[redacted]',
      ],
    })
    expect(event.$set_once.$initial_current_url).not.toContain(TOKEN)
  })

  test('replaces the token anywhere in an error report', () => {
    const timestamp = new Date()

    const event = redactPrivateLinkTokens({
      request: { url: `https://baserow.io/template/crm/private-link/${TOKEN}` },
      breadcrumbs: [{ data: { to: `/template/crm/private-link/${TOKEN}` } }],
      timestamp,
      level: null,
    })

    expect(JSON.stringify(event)).not.toContain(TOKEN)
    expect(event.timestamp).toBe(timestamp)
  })
})
