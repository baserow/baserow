import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import {
  captureTemplateEvent,
  createTemplateSearchTracker,
} from '@baserow/modules/core/utils/templateAnalytics'

describe('templateAnalytics', () => {
  let posthog = null

  beforeEach(() => {
    vi.useFakeTimers()
    posthog = { capture: vi.fn() }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('captures nothing without PostHog, like on a self-hosted instance', () => {
    expect(() =>
      captureTemplateEvent(undefined, 'previewed', { id: 1, slug: 'a' })
    ).not.toThrow()
  })

  test.each([
    [{ type: undefined }, 'crm'],
    [{ type: 'user', listed: true }, 'crm'],
    [{ type: 'user', listed: false }, null],
  ])('names only an official or listed template: %o', (values, slug) => {
    captureTemplateEvent(posthog, 'previewed', {
      id: 1,
      slug: 'crm',
      ...values,
    })

    expect(posthog.capture.mock.calls[0][1].template_slug).toBe(slug)
  })

  test('captures a search once the user stopped typing, or a template is opened', () => {
    const track = createTemplateSearchTracker(posthog, 'public')

    track('c', 9)
    track(' crm ', 2)
    vi.advanceTimersByTime(1000)
    track('crm', 2)
    vi.advanceTimersByTime(1000)
    track('', 20)
    vi.advanceTimersByTime(1000)
    track('crm', 2)
    track.flush()

    const search = [
      'template_searched',
      { query: 'crm', result_count: 2, tab: 'public' },
    ]
    expect(posthog.capture.mock.calls).toEqual([search, search])
  })
})
