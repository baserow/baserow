import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { navigateToAssistantLocation } from '@baserow_enterprise/utils/assistantNavigation'
import { createRunsTestApp, destroyRunsTestApp } from '../assistantRunHelpers'

const workspace = { id: 1, name: 'Test workspace' }

describe('Kuma navigation targets', () => {
  let testApp, app, push

  beforeEach(() => {
    testApp = createRunsTestApp()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
    app = testApp.getApp()
    push = vi.spyOn(app.$router, 'push').mockResolvedValue()
  })

  afterEach(() => destroyRunsTestApp(testApp))

  test.each([
    {
      application: {
        type: 'builder',
        pages: [{ id: 20, name: 'Home', path: '/' }],
      },
      location: { type: 'builder-page', application_id: 10, page_id: 20 },
      route: { name: 'builder-page', params: { builderId: 10, pageId: 20 } },
    },
    {
      application: {
        type: 'automation',
        workflows: [{ id: 20, name: 'My workflow' }],
      },
      location: {
        type: 'automation-workflow',
        automation_id: 10,
        workflow_id: 20,
      },
      route: {
        name: 'automation-workflow',
        params: { automationId: 10, workflowId: 20 },
      },
    },
    {
      application: { type: 'dashboard', widgets: [] },
      location: { type: 'dashboard', dashboard_id: 10 },
      route: { name: 'dashboard-application', params: { dashboardId: 10 } },
    },
  ])(
    'opens a loaded $location.type target without fetching it again',
    async ({ application, location, route }) => {
      await app.$store.dispatch('application/forceCreate', {
        id: 10,
        name: 'Created by Kuma',
        order: 1,
        workspace,
        ...application,
      })

      await navigateToAssistantLocation(app, workspace.id, location, () => true)

      expect(push).toHaveBeenCalledExactlyOnceWith(route)
      expect(testApp.mock.history.get).toHaveLength(0)
    }
  )

  test('fetches a dashboard when its creation broadcast is missing', async () => {
    const dashboard = {
      id: 10,
      type: 'dashboard',
      name: 'Metrics',
      order: 1,
      workspace,
      widgets: [],
    }
    testApp.mock.onGet('/applications/10/').reply(200, dashboard)
    const navigation = navigateToAssistantLocation(
      app,
      workspace.id,
      { type: 'dashboard', dashboard_id: 10 },
      () => true
    )
    await vi.advanceTimersByTimeAsync(3500)
    await navigation

    expect(app.$store.getters['application/get'](10)).toBeDefined()
    expect(push).toHaveBeenCalledExactlyOnceWith({
      name: 'dashboard-application',
      params: { dashboardId: 10 },
    })
  })

  test('opens the sending workspace without loading an application', async () => {
    await navigateToAssistantLocation(
      app,
      workspace.id,
      { type: 'workspace' },
      () => true
    )

    expect(push).toHaveBeenCalledExactlyOnceWith({
      name: 'workspace',
      params: { workspaceId: 1 },
    })
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test.each(['unknown', 'constructor', '__proto__'])(
    'ignores an unsupported location type %s',
    async (type) => {
      await navigateToAssistantLocation(app, workspace.id, { type }, () => true)

      expect(push).not.toHaveBeenCalled()
      expect(testApp.mock.history.get).toHaveLength(0)
    }
  )

  test('a superseded navigation stops waiting without fetching or routing', async () => {
    const isCurrent = vi.fn().mockReturnValue(true)
    const navigation = navigateToAssistantLocation(
      app,
      workspace.id,
      { type: 'dashboard', dashboard_id: 10 },
      isCurrent
    )
    isCurrent.mockReturnValue(false)
    await vi.advanceTimersByTimeAsync(50)
    await navigation

    expect(push).not.toHaveBeenCalled()
    expect(testApp.mock.history.get).toHaveLength(0)
  })
})
