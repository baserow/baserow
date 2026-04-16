import APIDocsDatabase from '@baserow/modules/database/pages/APIDocsDatabase.vue'

import { MockServer } from '@baserow/test/fixtures/mockServer'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import MockAdapter from 'axios-mock-adapter'
import flushPromises from 'flush-promises'

describe('APIDocsDatabase', () => {
  let mock = null
  let mockServer = null

  beforeEach(() => {
    const { $client, $store } = useNuxtApp()

    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
    mockServer = new MockServer(mock, $store)
  })

  afterEach(() => {
    mock.restore()
  })

  const mountComponent = async (databaseId) => {
    return await mountSuspended(APIDocsDatabase, {
      route: `/api-docs/database/${databaseId}`,
      global: {
        stubs: {
          Logo: { template: '<div />' },
          Button: { template: '<button><slot /></button>' },
          APIDocsSelectDatabase: { template: '<div />' },
          APIDocsIntro: { template: '<div />' },
          APIDocsAuth: { template: '<div />' },
          APIDocsTableFields: { template: '<div />' },
          APIDocsTableListFields: { template: '<div />' },
          APIDocsTableListRows: { template: '<div />' },
          APIDocsTableGetRow: { template: '<div />' },
          APIDocsTableCreateRow: { template: '<div />' },
          APIDocsTableUpdateRow: { template: '<div />' },
          APIDocsTableMoveRow: { template: '<div />' },
          APIDocsTableDeleteRow: { template: '<div />' },
          APIDocsTablePasswordFieldAuthentication: { template: '<div />' },
          APIDocsUploadFile: { template: '<div />' },
          APIDocsListTables: { template: '<div />' },
          APIDocsUploadFileViaURL: { template: '<div />' },
          APIDocsFilters: { template: '<div />' },
          APIDocsErrors: { template: '<div />' },
          APIDocsMenu: { template: '<div />' },
        },
      },
    })
  }

  test('clicking the database toggle opens the sidebar', async () => {
    mockServer.fakeSettings()
    mockServer.fakeAuthentication()

    const table = mockServer.createTable(1, 'Contacts')
    const { application } = await mockServer.createAppAndWorkspace(table)

    mockServer.createFields(application, table, [
      {
        name: 'Name',
        type: 'text',
        primary: true,
        read_only: false,
      },
    ])

    const wrapper = await mountComponent(application.id)

    expect(wrapper.find('.api-docs__databases').attributes('style')).toContain(
      'display: none;'
    )

    await wrapper.find('.api-docs__switch').trigger('click')
    await flushPromises()

    expect(
      wrapper.find('.api-docs__databases').attributes('style')
    ).toBeUndefined()
  })
})
