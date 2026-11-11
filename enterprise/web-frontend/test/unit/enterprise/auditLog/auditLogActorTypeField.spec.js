import { mountSuspended } from '@nuxt/test-utils/runtime'

import AuditLogActorTypeField from '@baserow_enterprise/components/auditLog/AuditLogActorTypeField'

const actorTypeNames = {
  'auth.User': 'User',
  'core.Agent': 'Agent',
}

async function mountComponent(type) {
  return await mountSuspended(AuditLogActorTypeField, {
    props: {
      row: { actor: type ? { type } : null },
      column: { key: 'actor_type' },
    },
    global: {
      mocks: {
        $registry: {
          exists(namespace, registeredType) {
            return namespace === 'subject' && registeredType in actorTypeNames
          },
          get(namespace, registeredType) {
            return {
              getTypeDisplayName: () => actorTypeNames[registeredType],
            }
          },
        },
      },
    },
  })
}

describe('AuditLogActorTypeField', () => {
  test.each([
    ['auth.User', 'User'],
    ['core.Agent', 'Agent'],
    ['custom.Robot', 'custom.Robot'],
  ])('renders the %s actor type', async (type, expected) => {
    const wrapper = await mountComponent(type)

    expect(wrapper.text()).toBe(expected)
    expect(wrapper.attributes('title')).toBe(expected)
  })

  test('renders an empty value for a legacy actor', async () => {
    const wrapper = await mountComponent(null)

    expect(wrapper.text()).toBe('')
    expect(wrapper.attributes('title')).toBe('')
  })
})
