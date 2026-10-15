import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import { AgentApplicationType } from '@baserow_enterprise/agent/applicationTypes'
import { selectAgentApplication } from '@baserow_enterprise/agent/middleware/selectAgentApplication'
import { RolePermissionManagerType } from '@baserow_enterprise/permissionManagerTypes'

describe('Opening an Agent from an unselected workspace', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test.each([true, false])(
    'loads workspace permissions before enforcing read access=%s',
    async (allowed) => {
      await testApp.store.dispatch('workspace/forceCreate', {
        id: 1,
        name: 'Workspace',
      })
      const agent = await testApp.store.dispatch('application/forceCreate', {
        id: 10,
        name: 'Support agent',
        type: 'agent',
        workspace: { id: 1 },
      })
      testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [
        {
          name: 'role',
          permissions: {
            'application.read': { default: allowed, exceptions: [] },
          },
        },
      ])
      testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
      const workspace = testApp.store.getters['workspace/get'](1)
      const manager = new RolePermissionManagerType({ app: testApp.nuxtApp })
      const app = {
        $store: testApp.store,
        $i18n: testApp.nuxtApp.$i18n,
        // Before selecting this workspace, only global permissions are available;
        // the workspace-specific operation is deliberately absent from them.
        $hasPermission: (operation, context, workspaceId) => {
          const permissions = workspace._.permissionsLoaded
            ? workspace._.permissions.find(({ name }) => name === 'role')
                .permissions
            : {}
          return manager.hasPermission(
            permissions,
            operation,
            context,
            workspaceId
          )
        },
      }
      app.$router = { push: vi.fn((to) => selectAgentApplication(app, to)) }
      const type = new AgentApplicationType({ app })
      expect(workspace._.permissionsLoaded).toBe(false)
      expect(type.isVisible(agent)).toBe(false)

      const opening = type.select(agent)
      if (allowed) {
        expect(await opening).toBe(true)
        expect(testApp.store.getters['application/getSelected'].id).toBe(10)
        expect(testApp.store.getters['workspace/getSelected'].id).toBe(1)
      } else {
        await expect(opening).rejects.toMatchObject({ statusCode: 404 })
        expect(testApp.store.getters['application/getSelected']).toBeNull()
      }
      expect(app.$router.push).toHaveBeenCalledTimes(1)
      expect(app.$router.push).toHaveBeenCalledWith({
        name: 'agent-application',
        params: { agentId: 10 },
      })
      expect(workspace._.permissionsLoaded).toBe(true)
      expect(
        testApp.mock.history.get.filter(({ url }) =>
          url.endsWith('/permissions/')
        )
      ).toHaveLength(1)
      expect(type.isVisible(agent)).toBe(allowed)
    }
  )
})
