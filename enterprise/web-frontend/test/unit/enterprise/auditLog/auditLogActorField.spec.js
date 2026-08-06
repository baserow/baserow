import { mountSuspended } from '@nuxt/test-utils/runtime'

import AuditLogActorField from '@baserow_enterprise/components/auditLog/AuditLogActorField'

async function mountComponent(actor, user = '') {
  return await mountSuspended(AuditLogActorField, {
    props: {
      row: { actor, user },
      column: { key: 'user' },
    },
    global: {
      mocks: {
        $t(key, params) {
          if (key === 'auditLog.actorDisplay') {
            return `${params.name} (${params.id})`
          }
          return key
        },
      },
    },
  })
}

describe('AuditLogActorField', () => {
  test.each([
    ['auth.User', 'user@example.com', 12, 'user@example.com (12)'],
    ['core.Agent', 'Row writer', 34, 'Row writer (34)'],
    ['custom.Robot', 'Robot', 56, 'Robot (56)'],
  ])('renders the %s actor type', async (type, name, id, expected) => {
    const wrapper = await mountComponent({ type, name, id })

    expect(wrapper.text()).toBe(expected)
    expect(wrapper.attributes('title')).toBe(expected)
  })

  test('keeps the legacy display while an actor is unavailable', async () => {
    const wrapper = await mountComponent(null, 'Legacy actor')

    expect(wrapper.text()).toBe('Legacy actor')
  })
})
