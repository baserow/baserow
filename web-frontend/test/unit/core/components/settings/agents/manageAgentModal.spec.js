import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

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

const ButtonStub = {
  props: { buttonType: { type: String, default: null } },
  template: '<button :type="buttonType"><slot /></button>',
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
              Button: ButtonStub,
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

  test('saves pages independently, retains drafts on failure, and stays open', async () => {
    const dispatch = vi.fn().mockResolvedValue({ id: 42 })
    const hide = vi.fn()
    const handleError = vi.fn()
    const teamsSetting = {
      ...generalSetting,
      name: 'Teams',
      getType: () => 'teams',
      getInitialValues: (agent) => ({
        team_ids: (agent?.teams || []).map((team) => team.id),
      }),
      getSubmitValues: ({ team_ids: teamIds }) => ({ team_ids: teamIds }),
      component: {
        props: ['modelValue'],
        emits: ['update:modelValue'],
        template: `<input class="teams-input" :value="modelValue.team_ids.join(',')"
          @input="$emit('update:modelValue', { ...modelValue, team_ids: [$event.target.valueAsNumber] })" type="number" />`,
      },
    }
    const wrapper = await mountSuspended(
      {
        components: {
          ManageAgentModal: {
            ...ManageAgentModal,
            methods: { ...ManageAgentModal.methods, hide, handleError },
          },
        },
        data: () => ({
          agent: {
            id: 42,
            name: 'Researcher',
            role_uid: 'MEMBER',
            teams: [],
          },
        }),
        template:
          '<ManageAgentModal ref="modal" :workspace="{ id: 12 }" :agent="agent" />',
        mounted() {
          this.$refs.modal.show()
        },
      },
      {
        global: {
          mocks: {
            $registry: {
              getOrderedList: () => [
                generalSetting,
                teamsSetting,
                new McpServerAgentSettingsType({
                  app: { $i18n: { t: (key) => key } },
                }),
              ],
            },
            $store: { dispatch },
            $t: (key) => key,
          },
          stubs: {
            Modal: modalStub,
            Error: true,
            Alert: {
              template: '<div class="success"><slot name="title" /></div>',
            },
            FormGroup: { template: '<div><slot /></div>' },
            FormInput: {
              props: ['modelValue'],
              emits: ['update:modelValue'],
              template:
                '<input class="name-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
              methods: { focus() {} },
            },
            Button: ButtonStub,
            WorkspaceRoleSelector: WorkspaceRoleSelectorStub,
          },
        },
      }
    )
    try {
      const pages = wrapper.findAll('.modal-sidebar__nav-link')
      await wrapper.find('.name-input').setValue('Renamed')
      await wrapper.setData({
        agent: {
          id: 42,
          name: 'Remote edit',
          role_uid: 'MEMBER',
          teams: [{ id: 5 }],
        },
      })
      expect(wrapper.find('.name-input').element.value).toBe('Renamed')
      await pages[1].trigger('click')
      expect(wrapper.find('.teams-input').element.value).toBe('')
      await wrapper.find('.teams-input').setValue('7')
      await wrapper.find('form').trigger('submit')
      await flushPromises()
      expect(dispatch).toHaveBeenLastCalledWith('agent/update', {
        agentId: 42,
        values: { team_ids: [7] },
      })
      expect(wrapper.find('.success').text()).toBe('agents.saved')
      expect(hide).not.toHaveBeenCalled()

      await pages[0].trigger('click')
      expect(wrapper.find('.name-input').element.value).toBe('Renamed')
      expect(wrapper.find('.success').exists()).toBe(false)
      dispatch.mockRejectedValueOnce(new Error('Failed'))
      await wrapper.find('form').trigger('submit')
      await flushPromises()
      expect(handleError).toHaveBeenCalledOnce()
      expect(wrapper.find('.name-input').element.value).toBe('Renamed')
      expect(wrapper.find('.success').exists()).toBe(false)
      await wrapper.find('form').trigger('submit')
      await flushPromises()
      expect(dispatch).toHaveBeenLastCalledWith('agent/update', {
        agentId: 42,
        values: { name: 'Renamed' },
      })
      expect(hide).not.toHaveBeenCalled()
      await pages[1].trigger('click')
      expect(wrapper.find('.teams-input').element.value).toBe('7')
      await wrapper.find('form').trigger('submit')
      expect(dispatch).toHaveBeenCalledTimes(3)
      await pages[2].trigger('click')
      expect(wrapper.findAll('button').map((button) => button.text())).toEqual([
        'action.close',
      ])
    } finally {
      wrapper.unmount()
    }
  })

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
          Button: ButtonStub,
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
          Button: ButtonStub,
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
  const setting = {
    component: AgentGeneralSettingsForm,
    componentPadding: true,
    name: 'General',
    showInCreate: true,
    getType: () => 'general',
    isActive: () => true,
    getInitialValues: () => ({ name: '', role_uid: 'MEMBER' }),
    getSubmitValues: ({ name, role_uid: roleUid }) => ({
      name,
      role_uid: roleUid,
    }),
  }
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
        mocks: {
          $registry: { getOrderedList: () => [setting] },
          $t: (key) => key,
        },
        stubs: {
          Modal: { template: '<div><slot name="content" /></div>' },
          Error: true,
          FormGroup: { template: '<div><slot /></div>' },
          FormInput: true,
          WorkspaceRoleSelector: WorkspaceRoleSelectorStub,
        },
      },
    }
  )
  try {
    const cancel = wrapper
      .findAll('button')
      .find((button) => button.text() === 'action.cancel')
    const create = wrapper
      .findAll('button')
      .find((button) => button.text() === 'agents.create')
    expect(cancel.attributes('type')).toBe('button')
    expect(create.attributes('type')).toBe('submit')
    cancel.element.click()
    expect(hide).toHaveBeenCalledOnce()
    expect(submit).not.toHaveBeenCalled()
  } finally {
    wrapper.unmount()
  }
})
