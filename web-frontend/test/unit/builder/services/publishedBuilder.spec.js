import { describe, expect, test, vi } from 'vitest'

import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'

const makeClient = () => ({
  get: vi.fn(),
  post: vi.fn(),
})

describe('PublishedBuilderService', () => {
  test('uses published routes without a preview builder', () => {
    const client = makeClient()
    const service = PublishedBuilderService(client)

    service.fetchElements({ id: 10 })
    service.fetchDataSources(10)
    service.fetchWorkflowActions(10)
    service.dispatchAll(10, {})

    expect(client.get.mock.calls.map(([url]) => url)).toEqual([
      'builder/domains/published/page/10/elements/',
      'builder/domains/published/page/10/data_sources/',
      'builder/domains/published/page/10/workflow_actions/',
    ])
    expect(client.post.mock.calls[0][0]).toBe(
      'builder/domains/published/page/10/dispatch-data-sources/'
    )
  })

  test('uses builder-scoped routes for every preview render request', () => {
    const client = makeClient()
    const service = PublishedBuilderService(client)

    service.fetchElements({ id: 10 }, 42)
    service.fetchDataSources(10, 42)
    service.fetchWorkflowActions(10, 42)
    service.dispatch(20, {}, {}, null, 42)
    service.dispatchAll(10, {}, 42)

    expect(client.get.mock.calls.map(([url]) => url)).toEqual([
      'builder/preview/42/pages/10/elements/',
      'builder/preview/42/pages/10/data-sources/',
      'builder/preview/42/pages/10/workflow-actions/',
    ])
    expect(client.post.mock.calls.map(([url]) => url)).toEqual([
      'builder/preview/42/data-sources/20/dispatch/',
      'builder/preview/42/pages/10/dispatch-data-sources/',
    ])
  })
})
