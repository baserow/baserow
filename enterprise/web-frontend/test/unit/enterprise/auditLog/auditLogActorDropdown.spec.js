import { mountSuspended } from '@nuxt/test-utils/runtime'
import flushPromises from 'flush-promises'

import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import AuditLogActorDropdown from '@baserow_enterprise/components/auditLog/AuditLogActorDropdown'

const actors = [
  {
    id: 'auth.User:1',
    subject_id: 1,
    subject_type: 'auth.User',
    label: 'user@example.com',
  },
  {
    id: 'core.Agent:1',
    subject_id: 1,
    subject_type: 'core.Agent',
    label: 'Row writer',
  },
]

async function mountComponent(fetchPage = null) {
  return await mountSuspended(AuditLogActorDropdown, {
    props: {
      fetchPage:
        fetchPage ||
        (() =>
          Promise.resolve({ data: { count: actors.length, results: actors } })),
    },
    global: {
      mocks: {
        $t(key) {
          return {
            'auditLog.allActors': 'All Actors',
          }[key]
        },
      },
    },
  })
}

describe('AuditLogActorDropdown', () => {
  test('renders users and agents in separate sections and selects an agent', async () => {
    const wrapper = await mountComponent()
    await wrapper.findComponent(PaginatedDropdown).vm.fetch()
    await flushPromises()

    expect(wrapper.html()).toMatchSnapshot()

    await wrapper.findAll('.select__item-link')[2].trigger('click')

    expect(wrapper.emitted('input')).toEqual([[{ id: 1, type: 'core.Agent' }]])
  })

  test('forwards the search query to the actor endpoint', async () => {
    const fetchPage = vi.fn(() =>
      Promise.resolve({ data: { count: 0, results: [] } })
    )
    const wrapper = await mountComponent(fetchPage)
    const dropdown = wrapper.findComponent(PaginatedDropdown)

    await dropdown.vm.fetch(1, 'robot')

    expect(fetchPage).toHaveBeenCalledWith(1, 'robot')
  })
})
