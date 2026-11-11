import flushPromises from 'flush-promises'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { AgentExtensionType } from '@baserow/modules/core/agentExtensionTypes'
import AgentsTable from '@baserow/modules/core/components/settings/agents/AgentsTable'
import MembersTable from '@baserow/modules/core/components/settings/members/MembersTable'
import { MembersPagePluginType } from '@baserow/modules/database/membersPagePluginTypes'
import { TestApp } from '@baserow/test/helpers/testApp'

// Renders the props a row expansion component receives.
const ExpandedRows = {
  name: 'ExpandedRows',
  props: ['row', 'columns', 'workspace', 'subjectId', 'kind'],
  template:
    '<tr class="expanded-rows"><td>{{ kind }}:{{ subjectId }}:{{ workspace.id }}:{{ columns.length > 0 }}</td></tr>',
}

const getRowExpansion = (columnKey, kind, getSubjectId) => ({
  component: ExpandedRows,
  columnKey,
  isExpandable: (row) => row.role_assignment_count > 0,
  getToggleLabel: (row) => `+${row.role_assignment_count}`,
  getProps: (row) => ({ kind, subjectId: getSubjectId(row) }),
})

class ExpandingMembersPlugin extends MembersPagePluginType {
  static getType() {
    return 'expanding_members_test'
  }

  isDeactivated() {
    return false
  }

  getRowExpansion() {
    return getRowExpansion('email', 'member', (row) => row.user_id)
  }
}

class ExpandingAgentsExtension extends AgentExtensionType {
  static getType() {
    return 'expandingAgentsTest'
  }

  getRowExpansion() {
    return getRowExpansion('name', 'agent', (row) => row.id)
  }
}

const workspace = { id: 1, name: 'Design', users: [], _: { roles: [] } }

/**
 * Returns the labels of the expansion toggles, and what the plugin's component
 * renders before and after expanding the first toggled row.
 */
async function expandFirstRow(wrapper) {
  const toggles = wrapper.findAll('.data-table__expand')
  const renderedBeforeExpanding = wrapper.find('.expanded-rows').exists()
  await toggles[0].trigger('click')
  await flushPromises()
  return {
    labels: toggles.map((toggle) => toggle.text()),
    renderedBeforeExpanding,
    expanded: wrapper.get('.expanded-rows').text(),
  }
}

describe('Management table row expansion', () => {
  let app

  beforeEach(() => {
    app = new TestApp()
  })

  afterEach(async () => {
    await app.afterEach()
  })

  test('members rows expand as the first active members plugin says', async () => {
    const plugin = new ExpandingMembersPlugin({ app: app.getApp() })
    app.$registry.register('membersPagePlugins', plugin)
    app.mock.onGet('/workspaces/users/workspace/1/').reply(200, [
      {
        id: 10,
        user_id: 42,
        name: 'Alex',
        email: 'alex@example.com',
        permissions: 'MEMBER',
        role_assignment_count: 2,
      },
      {
        id: 11,
        user_id: 43,
        name: 'Sam',
        email: 'sam@example.com',
        permissions: 'MEMBER',
        role_assignment_count: 0,
      },
    ])
    try {
      const wrapper = await app.mount(MembersTable, {
        props: { workspace },
        global: { mocks: { $hasPermission: () => true } },
      })
      await flushPromises()

      // Only the member with roles can be expanded.
      expect(await expandFirstRow(wrapper)).toEqual({
        labels: ['+2'],
        renderedBeforeExpanding: false,
        expanded: 'member:42:1:true',
      })
    } finally {
      app.$registry.unregister('membersPagePlugins', plugin.getType())
    }
  })

  test('agents rows expand as the first active agent extension says', async () => {
    const extension = new ExpandingAgentsExtension({ app: app.getApp() })
    app.$registry.register('agentExtension', extension)
    app.mock.onGet('/agents/workspace/1/').reply(200, {
      count: 2,
      results: [
        {
          id: 5,
          name: 'Writer',
          role_uid: 'NO_ACCESS',
          role_assignment_count: 2,
        },
        {
          id: 6,
          name: 'Reader',
          role_uid: 'NO_ACCESS',
          role_assignment_count: 0,
        },
      ],
    })
    try {
      const wrapper = await app.mount(AgentsTable, {
        props: { workspace },
        global: { mocks: { $hasPermission: () => true } },
      })
      await flushPromises()

      // Only the agent with roles can be expanded.
      expect(await expandFirstRow(wrapper)).toEqual({
        labels: ['+2'],
        renderedBeforeExpanding: false,
        expanded: 'agent:5:1:true',
      })
    } finally {
      app.$registry.unregister('agentExtension', extension.getType())
    }
  })
})
