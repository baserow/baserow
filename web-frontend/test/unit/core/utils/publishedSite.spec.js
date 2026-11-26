import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import posthog from 'posthog-js'

import {
  getPosthogOptions,
  getPublishedPageViewProperties,
  getReplayOptions,
  isPublishedSite,
  isWebFrontendHostname,
  publishedSiteBeforeSend,
} from '@baserow/modules/core/utils/publishedSite'
import { redactPrivateLinks } from '@baserow/modules/core/utils/templatePrivateLink'

const CONFIG = {
  publicWebFrontendUrl: 'https://baserow.io',
  extraPublicWebFrontendHostnames: ['app.baserow.io'],
  builderPreviewUrl: 'https://preview.baserow.io',
}

describe('isWebFrontendHostname', () => {
  test.each([
    ['baserow.io', true],
    ['app.baserow.io', true],
    ['preview.baserow.io', false],
    ['events.baserow.site', false],
    ['www.example.com', false],
  ])('%s is %s', (hostname, expected) => {
    expect(isWebFrontendHostname(hostname, CONFIG)).toBe(expected)
  })

  test('works without extra hostnames', () => {
    const config = { publicWebFrontendUrl: 'http://localhost:3000' }

    expect(isWebFrontendHostname('localhost', config)).toBe(true)
    expect(isWebFrontendHostname('events.localhost', config)).toBe(false)
  })
})

describe('isPublishedSite', () => {
  test.each([
    ['baserow.io', false],
    ['app.baserow.io', false],
    ['preview.baserow.io', false],
    ['events.baserow.site', true],
    ['www.example.com', true],
  ])('%s is %s', (hostname, expected) => {
    expect(isPublishedSite(hostname, CONFIG)).toBe(expected)
  })

  test('works without extra hostnames and preview URL', () => {
    const config = { publicWebFrontendUrl: 'http://localhost:3000' }

    expect(isPublishedSite('localhost', config)).toBe(false)
    expect(isPublishedSite('events.localhost', config)).toBe(true)
  })
})

describe('getPosthogOptions', () => {
  test('keeps the options of Baserow itself', () => {
    expect(
      getPosthogOptions({
        host: 'https://eu.posthog.com',
        publishedSite: false,
      })
    ).toStrictEqual({
      api_host: 'https://eu.posthog.com',
      capture_pageview: false,
      capture_pageleave: false,
      disable_session_recording: true,
      autocapture: {
        css_selector_allowlist: ['[ph-autocapture]'],
      },
      before_send: redactPrivateLinks,
    })
  })

  test('collects nothing but anonymous page views on a published site', () => {
    expect(
      getPosthogOptions({ host: 'https://eu.posthog.com', publishedSite: true })
    ).toStrictEqual({
      api_host: 'https://eu.posthog.com',
      cookieless_mode: 'always',
      person_profiles: 'never',
      capture_pageview: false,
      capture_pageleave: false,
      autocapture: false,
      disable_session_recording: true,
      disable_surveys: true,
      disable_product_tours: true,
      advanced_disable_flags: true,
      disable_external_dependency_loading: true,
      capture_heatmaps: false,
      capture_dead_clicks: false,
      capture_exceptions: false,
      capture_performance: false,
      before_send: publishedSiteBeforeSend,
    })
  })
})

describe('publishedSiteBeforeSend', () => {
  test.each(['$autocapture', '$$heatmap', '$identify', '$pageleave', 'custom'])(
    'drops the %s event',
    (event) => {
      expect(publishedSiteBeforeSend({ event, properties: {} })).toBeNull()
    }
  )

  test('keeps only the anonymous properties of a page view', () => {
    const event = publishedSiteBeforeSend({
      uuid: 'uuid',
      event: '$pageview',
      timestamp: 'timestamp',
      properties: {
        token: 'phc_test',
        // The identifier that a visit before the change stored in the browser.
        distinct_id: '019ac0de-0000-7000-8000-000000000000',
        $cookieless_mode: true,
        $cookieless_extra: 'events.baserow.site',
        $process_person_profile: false,
        $raw_user_agent: 'Mozilla/5.0',
        $host: 'events.baserow.site',
        $current_url: 'https://events.baserow.site/event/:id',
        $pathname: '/event/:id',
        $referring_domain: 'www.google.com',
        $browser: 'Chrome',
        $os: 'Mac OS X',
        $device_type: 'Desktop',
        $lib: 'web',
        $lib_version: '1.422.5',
        $insert_id: 'insert',
        $time: 1,
        $referrer: 'https://www.google.com/search?q=jane',
        $timezone: 'Europe/Vienna',
        $browser_language: 'de-AT',
        $screen_height: 1080,
        $viewport_width: 1280,
        $prev_pageview_pathname: '/event/5',
        $session_id: 'session',
        $device_id: 'device',
        title: 'Jane Doe',
      },
      $set: { email: 'jane@example.com' },
      $set_once: { $initial_referrer: 'https://www.google.com/search?q=jane' },
    })

    expect(event).toStrictEqual({
      uuid: 'uuid',
      event: '$pageview',
      timestamp: 'timestamp',
      properties: {
        token: 'phc_test',
        $cookieless_mode: true,
        $cookieless_extra: 'events.baserow.site',
        $process_person_profile: false,
        $raw_user_agent: 'Mozilla/5.0',
        $host: 'events.baserow.site',
        $current_url: 'https://events.baserow.site/event/:id',
        $pathname: '/event/:id',
        $referring_domain: 'www.google.com',
        $browser: 'Chrome',
        $os: 'Mac OS X',
        $device_type: 'Desktop',
        $lib: 'web',
        $lib_version: '1.422.5',
        $insert_id: 'insert',
        $time: 1,
        distinct_id: '$posthog_cookieless',
      },
    })
  })
})

describe('getPublishedPageViewProperties', () => {
  test('uses the path of the page instead of the visited URL', () => {
    const location = new URL('https://events.baserow.site/event/5?email=a@b.c')

    expect(
      getPublishedPageViewProperties(location, { id: 1, path: '/event/:id' })
    ).toStrictEqual({
      $current_url: 'https://events.baserow.site/event/:id',
      $pathname: '/event/:id',
      $cookieless_extra: 'events.baserow.site',
    })
  })
})

describe('getReplayOptions', () => {
  test('keeps the session in the session storage on Baserow itself', () => {
    expect(getReplayOptions({ publishedSite: false })).toStrictEqual({
      maskAllText: true,
      blockAllMedia: true,
    })
  })

  test('does not store the session on a published site', () => {
    expect(getReplayOptions({ publishedSite: true })).toStrictEqual({
      maskAllText: true,
      blockAllMedia: true,
      stickySession: false,
    })
  })
})

describe('PostHog on a published site', () => {
  const TOKEN = 'phc_test'
  const STORAGE_KEY = `ph_${TOKEN}_posthog`

  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('{}')))
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  test('removes what was stored before and sends an anonymous page view', () => {
    // What a visit before the change left in the browser. PostHog reads it
    // before removing it, including the features its project had enabled.
    const stored = JSON.stringify({
      distinct_id: 'old',
      $product_tours_enabled_server_side: true,
    })
    document.cookie = `${STORAGE_KEY}=${encodeURIComponent(stored)}; path=/`
    localStorage.setItem(STORAGE_KEY, stored)
    expect(document.cookie).toContain(STORAGE_KEY)

    const captured = []
    const instance = posthog.init(
      TOKEN,
      {
        ...getPosthogOptions({
          host: 'http://localhost:9999',
          publishedSite: true,
        }),
        // The browser of the tests is seen as a bot, whose events are dropped.
        opt_out_useragent_filter: true,
      },
      'publishedSite'
    )
    instance.on('eventCaptured', (event) => captured.push(event))

    instance.capture(
      '$pageview',
      getPublishedPageViewProperties(
        {
          origin: 'https://events.baserow.site',
          hostname: 'events.baserow.site',
        },
        { path: '/event/:id' }
      )
    )
    instance.capture('custom', { email: 'jane@example.com' })
    instance.identify('jane@example.com')

    // No script of PostHog is loaded, like the one of the product tours.
    expect(
      document.querySelectorAll('script[src*="localhost:9999"]')
    ).toHaveLength(0)
    expect(document.cookie).not.toContain('ph_')
    expect(
      Object.keys(localStorage).filter((key) => key.startsWith('ph_'))
    ).toStrictEqual([])
    expect(
      Object.keys(sessionStorage).filter((key) => key.startsWith('ph_'))
    ).toStrictEqual([])

    expect(captured).toHaveLength(1)
    expect(captured[0].event).toBe('$pageview')
    expect(captured[0].$set).toBeUndefined()
    expect(captured[0].$set_once).toBeUndefined()
    expect(captured[0].properties).toMatchObject({
      token: TOKEN,
      distinct_id: '$posthog_cookieless',
      $cookieless_mode: true,
      $cookieless_extra: 'events.baserow.site',
      $process_person_profile: false,
      $current_url: 'https://events.baserow.site/event/:id',
      $pathname: '/event/:id',
    })
    // Needed by PostHog to count the visitors of a day without a cookie.
    expect(captured[0].properties.$raw_user_agent).toBeTruthy()
    expect(captured[0].properties.$host).toBeTruthy()
  })
})

describe('isWebFrontendHostname with configured ports', () => {
  test.each([
    ['editor.example.com', true],
    ['studio.example.com', true],
    ['preview.example.com', false],
    ['editor.example.com.other.test', false],
  ])(
    'matches %s against the main and additional frontend hosts: %s',
    (hostname, expected) => {
      expect(
        isWebFrontendHostname(hostname, {
          publicWebFrontendUrl: 'https://editor.example.com:3000',
          extraPublicWebFrontendHostnames: ['studio.example.com'],
        })
      ).toBe(expected)
    }
  )

  test('accepts a configuration without additional hostnames', () => {
    expect(
      isWebFrontendHostname('editor.example.com', {
        publicWebFrontendUrl: 'https://editor.example.com',
      })
    ).toBe(true)
  })
})
