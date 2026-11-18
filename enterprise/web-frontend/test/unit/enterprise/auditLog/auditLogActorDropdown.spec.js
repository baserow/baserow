import { mountSuspended } from '@nuxt/test-utils/runtime'
import flushPromises from 'flush-promises'

import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import AuditLogActorDropdown from '@baserow_enterprise/components/auditLog/AuditLogActorDropdown'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes'

const actors = [
  {
    id: 'auth.User:1',
    actor_id: 1,
    actor_type: 'auth.User',
    value: 'user@example.com',
  },
  {
    id: 'auth.User:2',
    actor_id: 2,
    actor_type: 'auth.User',
    user_type: 'identity',
    value: 'Row writer',
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
            'subjectType.identities': 'Identities',
          }[key]
        },
      },
    },
  })
}

describe('AuditLogActorDropdown', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('renders users and identities in separate sections and selects an identity', async () => {
    const wrapper = await mountComponent()
    await wrapper.findComponent(PaginatedDropdown).vm.fetch()
    await flushPromises()

    expect(wrapper.html()).toMatchSnapshot()

    await wrapper.findAll('.select__item-link')[2].trigger('click')

    expect(wrapper.emitted('input')).toEqual([[{ id: 2, type: 'auth.User' }]])
  })

  test('shows identities with the icon of the user subject type', async () => {
    vi.spyOn(
      UserSubjectType.prototype,
      'identityIconClass',
      'get'
    ).mockReturnValue('iconoir-identity-test')
    const wrapper = await mountComponent()
    await wrapper.findComponent(PaginatedDropdown).vm.fetch()
    await flushPromises()

    expect(wrapper.find('.iconoir-identity-test').exists()).toBe(true)
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
