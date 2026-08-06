import { mountSuspended } from '@nuxt/test-utils/runtime'

import RoleAssignmentModal from '@baserow_enterprise/components/member-roles/RoleAssignmentModal'
import RoleSelector from '@baserow_enterprise/components/member-roles/RoleSelector'
import SelectAgentsList from '@baserow_enterprise/components/rbac/SelectAgentsList'

const SelectSubjectsListFooterStub = {
  name: 'SelectSubjectsListFooter',
  props: {
    subjectType: String,
    count: Number,
    showCommercialInfo: { type: Boolean, default: true },
  },
  emits: ['invite'],
  template: `
    <div>
      <span v-if="showCommercialInfo" class="commercial-info" />
      <button
        class="invite-agents"
        @click="$emit('invite', { uid: 'BUILDER' })"
      >
        {{ subjectType }}:{{ count }}
      </button>
    </div>
  `,
}

describe('SelectAgentsList', () => {
  test('selects and invites agents as Agent subjects', async () => {
    const agents = [
      { id: 1, name: 'Row writer' },
      { id: 2, name: 'Reviewer' },
    ]
    const wrapper = await mountSuspended(SelectAgentsList, {
      props: {
        agents,
        scopeType: 'application',
        showRoleSelector: true,
      },
      global: {
        stubs: { SelectSubjectsListFooter: SelectSubjectsListFooterStub },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()

    await wrapper.find('input[type="checkbox"]').setValue(true)
    expect(wrapper.find('.invite-agents').text()).toContain('core.Agent:1')

    await wrapper.find('.invite-agents').trigger('click')
    expect(wrapper.emitted('invite')).toEqual([
      [[agents[0]], { uid: 'BUILDER' }],
    ])
  })

  test('passes the commercial information option to the role context', async () => {
    const EditRoleContextStub = {
      props: {
        showCommercialInfo: { type: Boolean, default: true },
      },
      template:
        '<div><span v-if="showCommercialInfo" class="commercial-info" /></div>',
    }
    const role = { uid: 'BUILDER', name: 'Builder' }
    const wrapper = await mountSuspended(RoleSelector, {
      props: {
        value: role,
        roles: [role],
        workspace: { id: 1 },
        showCommercialInfo: false,
      },
      global: { stubs: { EditRoleContext: EditRoleContextStub } },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('is available from the role assignment modal', async () => {
    const agent = { id: 1, name: 'Row writer' }
    const role = { uid: 'BUILDER' }
    const wrapper = await mountSuspended(RoleAssignmentModal, {
      props: { agents: [agent], scopeType: 'application' },
      global: {
        mocks: {
          $featureFlagIsEnabled: (flag) => flag === 'agents',
        },
        stubs: {
          Modal: {
            methods: { hide() {} },
            template: '<div><slot /></div>',
          },
          SelectMembersList: true,
          SelectTeamsList: true,
          SelectAgentsList: {
            emits: ['invite'],
            template:
              '<button class="select-agent" @click="$emit(\'invite\', [agents[0]], role)">Select agent</button>',
            props: ['agents'],
            data: () => ({ role }),
          },
        },
      },
    })

    expect(wrapper.text()).toContain('roleAssignmentModal.agentsTab')

    const agentsTab = wrapper
      .findAll('.tabs__item')
      .find((tab) => tab.text() === 'roleAssignmentModal.agentsTab')
    await agentsTab.trigger('click')
    await wrapper.find('.select-agent').trigger('click')
    expect(wrapper.emitted('invite-agents')).toEqual([[[agent], role]])
  })

  test('hides the Agents tab when the feature flag is disabled', async () => {
    const wrapper = await mountSuspended(RoleAssignmentModal, {
      props: { scopeType: 'application' },
      global: {
        mocks: {
          $featureFlagIsEnabled: () => false,
        },
        stubs: {
          Modal: { template: '<div><slot /></div>' },
          SelectMembersList: true,
          SelectTeamsList: true,
          SelectAgentsList: true,
        },
      },
    })

    expect(wrapper.text()).not.toContain('roleAssignmentModal.agentsTab')
  })
})
