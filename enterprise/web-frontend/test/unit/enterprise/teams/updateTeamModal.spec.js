import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import UpdateTeamModal from '@baserow_enterprise/components/teams/UpdateTeamModal'

test.each([false, true])(
  'preserves memberships and prevents saving after a load failure: %s',
  async (loadFails) => {
    const subject = { subject_id: 201, subject_type: 'core.Agent' }
    const client = {
      get: vi.fn((url) => {
        if (loadFails && url.startsWith('/agents/')) {
          return Promise.reject({
            handler: {
              getMessage: () => ({
                title: 'Unable to load agents',
                message: 'Try again',
              }),
              handled: vi.fn(),
            },
          })
        }
        return Promise.resolve({
          data: url.startsWith('/agents/')
            ? { results: [], next: null }
            : [subject],
        })
      }),
      put: vi.fn().mockResolvedValue({ data: { id: 1, name: 'Renamed' } }),
    }
    const wrapper = await mountSuspended(
      {
        components: { UpdateTeamModal },
        data: () => ({
          workspace: { id: 12, users: [] },
          team: { id: 1, name: 'Team' },
        }),
        template:
          '<div><button class="open" @click="$refs.team.show()">Open</button><UpdateTeamModal ref="team" :workspace="workspace" :team="team" /></div>',
      },
      {
        global: {
          mocks: { $client: client },
          stubs: {
            Modal: {
              template: '<div><slot /></div>',
              methods: { show() {}, hide() {} },
            },
            MemberAssignmentModal: true,
            ManageTeamForm: {
              props: ['invitedSubjects', 'disabled'],
              methods: { reset() {} },
              template: `<div><span v-for="subject in invitedSubjects" :key="subject.id">{{ subject.name }}</span><button class="save" :disabled="disabled" @click="$emit('submitted', { name: 'Renamed', default_role: 'VIEWER', subjects: invitedSubjects.map(({subject_id, subject_type}) => ({subject_id, subject_type})) })">Save</button></div>`,
            },
          },
        },
      }
    )
    try {
      await wrapper.find('.open').trigger('click')
      await flushPromises()
      if (loadFails) {
        expect(wrapper.text()).toContain('Unable to load agents')
        expect(wrapper.find('.save').element.disabled).toBe(true)
        wrapper.find('.save').element.click()
        expect(client.put).not.toHaveBeenCalled()
        return
      }
      expect(wrapper.text()).toContain('(201)')
      await wrapper.find('.save').trigger('click')
      await flushPromises()
      expect(client.put).toHaveBeenCalledWith('/teams/1/', {
        name: 'Renamed',
        default_role: 'VIEWER',
        subjects: [subject],
      })
    } finally {
      wrapper.unmount()
    }
  }
)
