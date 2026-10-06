import { TestApp } from '@baserow/test/helpers/testApp'

describe('builderToast store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('info keeps the formats of the title and message on the toast', async () => {
    await store.dispatch('builderToast/info', {
      title: '**Saved**',
      titleFormat: 'markdown',
      message: 'Row created',
      messageFormat: 'markdown',
    })

    const [toast] = store.getters['builderToast/all']
    expect(toast).toMatchObject({
      type: 'info-primary',
      title: '**Saved**',
      titleFormat: 'markdown',
      message: 'Row created',
      messageFormat: 'markdown',
    })
  })

  test('info leaves the formats out when none are given', async () => {
    await store.dispatch('builderToast/info', {
      title: 'Saved',
      message: 'Row created',
    })

    const [toast] = store.getters['builderToast/all']
    expect(toast).not.toHaveProperty('titleFormat')
    expect(toast).not.toHaveProperty('messageFormat')
  })
})
