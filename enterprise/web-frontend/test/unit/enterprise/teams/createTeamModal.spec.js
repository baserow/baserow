import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import CreateTeamModal from '@baserow_enterprise/components/teams/CreateTeamModal'

test('creates the team with its name and role only', async () => {
  const team = { id: 3, name: 'Sales', default_role: 'EDITOR' }
  const client = { post: vi.fn().mockResolvedValue({ data: team }) }
  const wrapper = await mountSuspended(CreateTeamModal, {
    props: { workspace: { id: 12, users: [] } },
    global: {
      mocks: { $client: client },
      stubs: {
        Modal: {
          template: '<div><slot /></div>',
          methods: { show() {}, hide() {} },
        },
        ManageTeamForm: {
          methods: { reset() {} },
          template:
            "<button class=\"save\" @click=\"$emit('submitted', { name: 'Sales', default_role: 'EDITOR' })\">Save</button>",
        },
      },
    },
  })

  try {
    await wrapper.find('.save').trigger('click')
    await flushPromises()

    expect(client.post).toHaveBeenCalledWith('/teams/workspace/12/', {
      name: 'Sales',
      default_role: 'EDITOR',
    })
    expect(wrapper.emitted('created')).toEqual([[team]])
  } finally {
    wrapper.unmount()
  }
})
