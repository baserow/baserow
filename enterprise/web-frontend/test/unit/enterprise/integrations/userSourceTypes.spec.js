import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('LocalBaserowUserSourceType getSummary', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const seedBuilder = async (integration) => {
    await testApp.store.dispatch('application/forceCreate', {
      id: 1,
      name: 'Site',
      type: 'builder',
      workspace: { id: 1 },
      pages: [],
      integrations: [integration],
    })
  }

  const getSummary = (userSource) =>
    testApp
      .getRegistry()
      .get('userSource', 'local_baserow')
      .getSummary(userSource)

  test('summarises the selected table', async () => {
    await seedBuilder({
      id: 10,
      type: 'local_baserow',
      name: 'Local Baserow',
      context_data: {
        databases: [{ id: 5, tables: [{ id: 7, name: 'Users' }] }],
      },
    })

    expect(
      getSummary({
        application_id: 1,
        integration_id: 10,
        table_id: 7,
        email_field_id: 1,
        name_field_id: 2,
        user_count_updated_at: null,
      })
    ).toBe('Local Baserow - Users')
  })

  test('reports not configured when the integration has no databases', async () => {
    await seedBuilder({ id: 10, type: 'local_baserow', name: 'Local Baserow' })

    expect(
      getSummary({ application_id: 1, integration_id: 10, table_id: 7 })
    ).toBe('Local Baserow - localBaserowUserSourceType.notConfigured')
  })
})
