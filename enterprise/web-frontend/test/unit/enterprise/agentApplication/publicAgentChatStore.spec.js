import { TestApp } from '@baserow/test/helpers/testApp'

describe('publicAgentChat store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    store.commit('publicAgentChat/SET_CONVERSATION', {
      uuid: 'c1',
      messages: [],
      status: 'idle',
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('answer chunks replace the partial answer and the final message lands once', async () => {
    await store.dispatch('publicAgentChat/handleEvent', {
      type: 'ai/started',
      message_id: '7',
    })
    expect(store.getters['publicAgentChat/getStatus']).toBe('working')
    await store.dispatch('publicAgentChat/handleEvent', {
      type: 'ai/answer_chunk',
      content: 'Ac',
    })
    await store.dispatch('publicAgentChat/handleEvent', {
      type: 'ai/answer_chunk',
      content: 'Acme builds robots.',
    })
    expect(store.getters['publicAgentChat/getPartial']).toBe(
      'Acme builds robots.'
    )

    await store.dispatch('publicAgentChat/handleEvent', {
      type: 'ai/message',
      id: 7,
      content: 'Acme builds robots.',
    })
    await store.dispatch('publicAgentChat/handleEvent', {
      type: 'ai/message',
      id: 7,
      content: 'Acme builds robots.',
    })
    expect(store.getters['publicAgentChat/getPartial']).toBe('')
    expect(store.getters['publicAgentChat/getMessages']).toEqual([
      { key: 'm-7', id: 7, role: 'ai', content: 'Acme builds robots.' },
    ])

    // Only the coarse status reaches the page; errors carry no details.
    await store.dispatch('publicAgentChat/handleEvent', { type: 'ai/error' })
    expect(store.getters['publicAgentChat/getStatus']).toBe('error')
    await store.dispatch('publicAgentChat/handleStatus', 'waiting_for_approval')
    expect(store.getters['publicAgentChat/isBusy']).toBe(true)
    await store.dispatch('publicAgentChat/handleStatus', 'idle')
    expect(store.getters['publicAgentChat/isBusy']).toBe(false)
  })
})
