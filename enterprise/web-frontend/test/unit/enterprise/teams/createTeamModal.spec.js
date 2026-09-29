import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import CreateTeamModal from '@baserow_enterprise/components/teams/CreateTeamModal'

test('opens the user picker when loading agents fails', async () => {
  const handled = vi.fn()
  const client = {
    get: vi.fn().mockRejectedValue({
      handler: {
        getMessage: () => ({
          title: 'Unable to load agents',
          message: 'Try again',
        }),
        handled,
      },
    }),
  }
  const subjectTypes = {
    'auth.User': {
      type: 'auth.User',
      getId: (subject) => subject.user_id,
    },
    'core.Agent': {
      type: 'core.Agent',
      getId: (subject) => subject.id,
    },
  }
  const wrapper = await mountSuspended(CreateTeamModal, {
    props: {
      workspace: {
        id: 12,
        users: [{ user_id: 5, name: 'Workspace user' }],
      },
    },
    global: {
      mocks: {
        $client: client,
        $featureFlagIsEnabled: () => true,
        $hasPermission: () => true,
        $registry: { get: (_, type) => subjectTypes[type] },
        $t: (key) => key,
      },
      stubs: {
        Error: {
          props: ['error'],
          template: '<div v-if="error.visible">{{ error.title }}</div>',
        },
        Modal: { template: '<div><slot /></div>' },
        ManageTeamForm: {
          template:
            '<button class="invite" @click="$emit(\'invite\')">Invite</button>',
        },
        MemberAssignmentModal: {
          props: ['members'],
          data: () => ({ visible: false }),
          methods: {
            show() {
              this.visible = true
            },
          },
          template:
            '<div v-if="visible" class="picker"><span v-for="member in members" :key="member.id">{{ member.name }}</span></div>',
        },
      },
    },
  })

  try {
    await wrapper.find('.invite').trigger('click')
    await flushPromises()

    expect(client.get).toHaveBeenCalledWith('/agents/workspace/12/', {
      params: { size: 200, page: 1 },
    })
    expect(wrapper.find('.picker').text()).toContain('Workspace user')
    expect(wrapper.text()).toContain('Unable to load agents')
    expect(handled).toHaveBeenCalledOnce()
  } finally {
    wrapper.unmount()
  }
})
