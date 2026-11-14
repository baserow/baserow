import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import UpdateTeamModal from '@baserow_enterprise/components/teams/UpdateTeamModal'

const team = {
  id: 1,
  name: 'Team',
  default_role: 'EDITOR',
  subject_count: 1,
  subject_sample: [{ subject_type: 'auth.User', subject_label: 'Jeff' }],
}

function mountModal({ client = {}, hasPermission = () => true } = {}) {
  const hide = vi.fn()
  const mounted = mountSuspended(
    {
      components: { UpdateTeamModal },
      data: () => ({ workspace: { id: 12, users: [] }, team }),
      template:
        '<div><button class="open" @click="$refs.team.show()">Open</button><UpdateTeamModal ref="team" :workspace="workspace" :team="team" @updated="$emit(\'updated\', $event)" @manage-members="$emit(\'manage-members\', $event)" /></div>',
      emits: ['updated', 'manage-members'],
    },
    {
      global: {
        mocks: { $client: client, $hasPermission: hasPermission },
        stubs: {
          Modal: {
            template: '<div><slot /></div>',
            methods: { show() {}, hide },
          },
          ManageTeamForm: {
            methods: { reset() {} },
            template:
              "<div><slot /><button class=\"save\" @click=\"$emit('submitted', { name: 'Renamed', default_role: 'VIEWER' })\">Save</button></div>",
          },
        },
      },
    }
  )
  return { mounted, hide }
}

test('saves the name and role and leaves the members alone', async () => {
  const updated = { id: 1, name: 'Renamed', default_role: 'VIEWER' }
  const client = {
    get: vi.fn(),
    put: vi.fn().mockResolvedValue({ data: updated }),
  }
  const wrapper = await mountModal({ client }).mounted
  try {
    await wrapper.find('.open').trigger('click')
    await wrapper.find('.save').trigger('click')
    await flushPromises()

    expect(client.get).not.toHaveBeenCalled()
    expect(client.put).toHaveBeenCalledWith('/teams/1/', {
      name: 'Renamed',
      default_role: 'VIEWER',
    })
    expect(wrapper.emitted('updated')).toEqual([[updated]])
  } finally {
    wrapper.unmount()
  }
})

test('the members button closes the modal and asks for the members', async () => {
  const hasPermission = vi.fn().mockReturnValue(true)
  const { mounted, hide } = mountModal({ hasPermission })
  const wrapper = await mounted
  try {
    await wrapper.find('.open').trigger('click')
    const button = wrapper.find('.team-members-summary button')
    expect(button.text()).toBe('teamMembersSummary.manage')

    await button.trigger('click')

    expect(hasPermission).toHaveBeenCalledWith(
      'enterprise.teams.list_subjects',
      expect.objectContaining({ id: 12 }),
      12
    )
    expect(hide).toHaveBeenCalled()
    expect(wrapper.emitted('manage-members')).toEqual([[team]])
  } finally {
    wrapper.unmount()
  }
})

test('has no members button without the permission to list them', async () => {
  const wrapper = await mountModal({ hasPermission: () => false }).mounted
  try {
    await wrapper.find('.open').trigger('click')

    expect(wrapper.find('.team-members-summary').exists()).toBe(true)
    expect(wrapper.find('.team-members-summary button').exists()).toBe(false)
  } finally {
    wrapper.unmount()
  }
})
