import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'

/** A response the test releases when it chooses. */
const held = (body) => {
  let release = null
  const promise = new Promise((resolve) => {
    release = () => resolve([200, body])
  })
  return { reply: () => promise, release: () => release() }
}

const APPLICATION_ID = 100

describe('integration store', () => {
  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('application/forceCreate', {
      id: APPLICATION_ID,
      name: 'Customers',
      type: 'database',
      workspace: { id: 1 },
      tables: [],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const application = () => store.getters['application/get'](APPLICATION_ID)

  test('a fetch fills the application it names', async () => {
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(200, [{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])

    await store.dispatch('integration/fetch', { application: application() })

    expect(application().integrations.map((i) => i.name)).toEqual(['Bot'])
  })

  test('a delayed fetch does not erase an integration created after it started', async () => {
    // The response snapshots an empty list. By the time it lands the list
    // holds a bot, and replacing it with the snapshot loses that bot for
    // good: nothing refetches.
    const answer = held([])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(answer.reply)

    const fetching = store.dispatch('integration/fetch', {
      application: application(),
    })
    await flushPromises()
    await store.dispatch('integration/forceCreate', {
      application: application(),
      integration: { id: 9, type: 'slack_bot', name: 'Fresh bot', order: '1' },
    })

    answer.release()
    await fetching

    expect(application().integrations.map((i) => i.name)).toEqual(['Fresh bot'])
  })

  test('a fetch fills the application object the store holds now', async () => {
    // `forceSetAll` replaces every application object. Committing onto the
    // one the fetch started with fills a list nothing renders, and leaves the
    // one on screen empty.
    const answer = held([{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(answer.reply)

    const stale = application()
    const fetching = store.dispatch('integration/fetch', {
      application: stale,
    })
    await flushPromises()

    await store.dispatch('application/forceSetAll', {
      applications: [
        {
          id: APPLICATION_ID,
          name: 'Customers',
          type: 'database',
          workspace: { id: 1 },
          tables: [],
        },
      ],
    })

    answer.release()
    await fetching

    expect(application()).not.toBe(stale)
    expect(application().integrations.map((i) => i.name)).toEqual(['Bot'])
  })
})
