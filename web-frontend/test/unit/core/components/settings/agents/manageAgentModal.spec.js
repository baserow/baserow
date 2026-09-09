import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test, vi } from 'vitest'

import Button from '@baserow/modules/core/components/Button'
import ManageAgentModal from '@baserow/modules/core/components/settings/agents/ManageAgentModal'
import AgentGeneralSettingsForm from '@baserow/modules/core/components/settings/agents/AgentGeneralSettingsForm'
import { McpServerAgentSettingsType } from '@baserow/modules/core/agentSettingsTypes'

const WorkspaceRoleSelectorStub = {
  name: 'WorkspaceRoleSelector',
  props: {
    modelValue: { type: String, required: true },
    showCommercialInfo: { type: Boolean, default: true },
  },
  emits: ['update:modelValue'],
  template: `
    <div class="workspace-role-selector">
      <span v-if="showCommercialInfo" class="commercial-info" />
    </div>
  `,
}

describe('ManageAgentModal', () => {
  const generalSetting = {
    component: AgentGeneralSettingsForm,
    componentPadding: true,
    icon: 'iconoir-settings',
    name: 'General',
    showInCreate: true,
    getType: () => 'general',
    isActive: () => true,
    getInitialValues: (agent, { defaultRole }) => ({
      name: agent?.name || '',
      role_uid: agent?.role_uid || defaultRole,
    }),
    getSubmitValues: ({ name, role_uid: roleUid }) => ({
      name,
      role_uid: roleUid,
    }),
  }

  const modalStub = {
    methods: { show() {} },
    props: { leftSidebar: Boolean },
    template: `
      <div>
        <aside v-if="leftSidebar"><slot name="sidebar" /></aside>
        <main><slot name="content" /></main>
      </div>
    `,
  }

  test.each([
    [true, 'MEMBER'],
    [false, 'NO_ACCESS'],
  ])(
    'when No access is deactivated=%s, defaults to %s',
    async (isDeactivated, expectedRole) => {
      const wrapper = await mountSuspended(
        {
          components: { ManageAgentModal },
          data: () => ({
            workspace: {
              id: 12,
              _: {
                roles: [
                  { uid: 'MEMBER', isVisible: true },
                  { uid: 'NO_ACCESS', isVisible: true, isDeactivated },
                ],
              },
            },
          }),
          template:
            '<ManageAgentModal ref="agentModal" :workspace="workspace" />',
          mounted() {
            this.$refs.agentModal.show()
          },
        },
        {
          global: {
            mocks: {
              $registry: { getOrderedList: () => [generalSetting] },
              $t: (key) => key,
            },
            stubs: {
              Modal: modalStub,
              Error: true,
              FormGroup: { template: '<div><slot /></div>' },
              FormInput: {
                template: '<input />',
                methods: { focus() {} },
              },
              Button: { template: '<button><slot /></button>' },
              WorkspaceRoleSelector: {
                ...WorkspaceRoleSelectorStub,
                template: '<div class="selected-role">{{ modelValue }}</div>',
              },
            },
          },
        }
      )

      expect(wrapper.find('.selected-role').text()).toBe(expectedRole)
      wrapper.unmount()
    }
  )

  test('hides commercial information in its role selector', async () => {
    const wrapper = await mountSuspended(ManageAgentModal, {
      props: {
        workspace: { id: 12, _: { roles: [] } },
      },
      global: {
        mocks: {
          $registry: { getOrderedList: () => [generalSetting] },
          $t: (key) => key,
        },
        stubs: {
          Modal: modalStub,
          Error: true,
          FormGroup: { template: '<div><slot /></div>' },
          FormInput: true,
          Button: { template: '<button><slot /></button>' },
          WorkspaceRoleSelector: WorkspaceRoleSelectorStub,
        },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('shows registered settings in a sidebar when editing', async () => {
    const mcpSetting = new McpServerAgentSettingsType({
      app: { $i18n: { t: () => 'MCP server' } },
    })
    const teamsSetting = {
      ...generalSetting,
      component: { template: '<div class="teams-settings" />' },
      icon: 'iconoir-community',
      name: 'Teams',
      getType: () => 'teams',
      getInitialValues: () => ({ team_ids: [3] }),
      getSubmitValues: ({ team_ids: teamIds }) => ({ team_ids: teamIds }),
    }
    const wrapper = await mountSuspended(ManageAgentModal, {
      props: {
        workspace: { id: 12, _: { roles: [] } },
        agent: { id: 42, name: 'Researcher', role_uid: 'MEMBER' },
      },
      global: {
        mocks: {
          $registry: {
            getOrderedList: () => [generalSetting, teamsSetting, mcpSetting],
          },
          $t: (key) => key,
        },
        stubs: {
          Modal: modalStub,
          Error: true,
          FormGroup: { template: '<div><slot /></div>' },
          FormInput: true,
          Button: { template: '<button><slot /></button>' },
          WorkspaceRoleSelector: WorkspaceRoleSelectorStub,
        },
      },
    })

    await wrapper.findAll('.modal-sidebar__nav-link')[1].trigger('click')

    expect(wrapper.html()).toMatchSnapshot()
  })
})

test('Cancel closes the Agent modal without submitting', async () => {
  const submit = vi.fn()
  const hide = vi.fn()
  const wrapper = await mountSuspended(
    {
      ...ManageAgentModal,
      components: { ...ManageAgentModal.components, Button },
      methods: { ...ManageAgentModal.methods, submit, hide },
    },
    {
      attachTo: document.body,
      props: { workspace: { id: 12, _: { roles: [] } } },
      global: {
        mocks: { $registry: { getOrderedList: () => [] }, $t: (key) => key },
        stubs: {
          Modal: { template: '<div><slot name="content" /></div>' },
          Error: true,
        },
      },
    }
  )
  try {
    wrapper
      .findAll('button')
      .find((button) => button.text() === 'action.cancel')
      .element.click()
    expect(hide).toHaveBeenCalledOnce()
    expect(submit).not.toHaveBeenCalled()
  } finally {
    wrapper.unmount()
  }
})
