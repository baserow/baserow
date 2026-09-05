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

  test('a delayed fetch does not undo an edit made while it was open', async () => {
    // The response was written before the edit, so replacing the list with it
    // puts the old values back. The edit is saved on the server and looks
    // lost on screen, which for a bot's token reads as a missing credential.
    const answer = held([
      { id: 7, type: 'slack_bot', name: 'Bot', order: '1', token: '' },
    ])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(answer.reply)
    await store.dispatch('integration/forceCreate', {
      application: application(),
      integration: { id: 7, type: 'slack_bot', name: 'Bot', order: '1' },
    })

    const fetching = store.dispatch('integration/fetch', {
      application: application(),
    })
    await flushPromises()
    await store.dispatch('integration/forceUpdate', {
      application: application(),
      integration: { id: 7 },
      values: { token: 'xoxb-fresh' },
    })

    answer.release()

    expect(await fetching).toBeNull()
    expect(application().integrations.map((i) => i.token)).toEqual([
      'xoxb-fresh',
    ])
  })

  test('a delayed fetch does not undo a reorder made while it was open', async () => {
    const answer = held([
      { id: 7, type: 'slack_bot', name: 'First', order: '1' },
      { id: 8, type: 'slack_bot', name: 'Second', order: '2' },
    ])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(answer.reply)
    for (const integration of [
      { id: 7, type: 'slack_bot', name: 'First', order: '1' },
      { id: 8, type: 'slack_bot', name: 'Second', order: '2' },
    ]) {
      await store.dispatch('integration/forceCreate', {
        application: application(),
        integration,
      })
    }

    const fetching = store.dispatch('integration/fetch', {
      application: application(),
    })
    await flushPromises()
    await store.dispatch('integration/forceMove', {
      application: application(),
      integrationId: 8,
      beforeIntegrationId: 7,
    })

    answer.release()

    expect(await fetching).toBeNull()
    expect(application().integrations.map((i) => i.name)).toEqual([
      'Second',
      'First',
    ])
  })

  test('a fetch does not clear the way for another to drop a newer bot', async () => {
    // Two fetches overlap and a create lands while the first is writing its
    // answer. Restoring the counter afterwards drops that create's bump, so
    // the second fetch reads its own snapshot as current and writes a list
    // the new bot is not in.
    const first = held([{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .replyOnce(first.reply)
    const second = held([{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(second.reply)

    const fetchingFirst = store.dispatch('integration/fetch', {
      application: application(),
    })
    const fetchingSecond = store.dispatch('integration/fetch', {
      application: application(),
    })
    await flushPromises()

    // While the first fetch is writing, not after it has finished: that is
    // the window the restored counter reopened.
    let created = false
    const unsubscribe = store.subscribe(({ type }) => {
      if (type === 'integration/ADD_ITEM' && !created) {
        created = true
        store.dispatch('integration/forceCreate', {
          application: application(),
          integration: {
            id: 9,
            type: 'slack_bot',
            name: 'Fresh bot',
            order: '2',
          },
        })
      }
    })

    first.release()
    await fetchingFirst
    unsubscribe()

    second.release()

    expect(await fetchingSecond).toBeNull()
    expect(application().integrations.map((i) => i.name)).toContain('Fresh bot')
  })

  test('a fetch that backed off says it did not load the list', async () => {
    // Backing off leaves the list holding only what was created during the
    // request. A caller that reads this as a successful load would remember
    // the database as loaded and never see the rest.
    const answer = held([{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])
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

    expect(await fetching).toBeNull()
    expect(application().integrations.map((i) => i.name)).toEqual(['Fresh bot'])
  })
})
