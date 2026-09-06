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
    // holds a bot, and replacing it with the snapshot would lose that bot.
    // The retry sees what the server has by then.
    const answer = held([])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .replyOnce(answer.reply)
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(200, [{ id: 9, type: 'slack_bot', name: 'Fresh bot', order: '1' }])

    const fetching = store.dispatch('integration/fetch', {
      application: application(),
    })
    await flushPromises()
    await store.dispatch('integration/forceCreate', {
      application: application(),
      integration: { id: 9, type: 'slack_bot', name: 'Fresh bot', order: '1' },
    })

    answer.release()

    expect(await fetching).toEqual([
      { id: 9, type: 'slack_bot', name: 'Fresh bot', order: '1' },
    ])
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
      .replyOnce(answer.reply)
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(200, [
        {
          id: 7,
          type: 'slack_bot',
          name: 'Bot',
          order: '1',
          token: 'xoxb-fresh',
        },
      ])
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
    await fetching

    expect(application().integrations.map((i) => i.token)).toEqual([
      'xoxb-fresh',
    ])
  })

  test('a delayed fetch does not undo a reorder made while it was open', async () => {
    const stale = [
      { id: 7, type: 'slack_bot', name: 'First', order: '1' },
      { id: 8, type: 'slack_bot', name: 'Second', order: '2' },
    ]
    const answer = held(stale)
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .replyOnce(answer.reply)
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(200, [
        { id: 8, type: 'slack_bot', name: 'Second', order: '1' },
        { id: 7, type: 'slack_bot', name: 'First', order: '2' },
      ])
    for (const integration of stale) {
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
    await fetching

    expect(application().integrations.map((i) => i.name)).toEqual([
      'Second',
      'First',
    ])
  })

  test('a fetch does not clear the way for another to drop a newer bot', async () => {
    // Two fetches overlap and a create lands while the first is writing its
    // answer. Restoring the counter afterwards would drop that create's bump,
    // leaving the second fetch to write a list the new bot is not in.
    const first = held([{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])
    const second = held([{ id: 7, type: 'slack_bot', name: 'Bot', order: '1' }])
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .replyOnce(first.reply)
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .replyOnce(second.reply)
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(200, [
        { id: 7, type: 'slack_bot', name: 'Bot', order: '1' },
        { id: 9, type: 'slack_bot', name: 'Fresh bot', order: '2' },
      ])

    const fetchingFirst = store.dispatch('integration/fetch', {
      application: application(),
    })
    const fetchingSecond = store.dispatch('integration/fetch', {
      application: application(),
    })
    await flushPromises()

    // While the first fetch is writing, not after it has finished: that is
    // the window a restored counter reopened.
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
    await fetchingSecond

    expect(application().integrations.map((i) => i.name)).toContain('Fresh bot')
  })

  test('a list that never settles says it did not load', async () => {
    // Something writes to the list during every attempt, so no answer is ever
    // current. A caller that read this as a successful load would remember the
    // application as loaded and never see the rest.
    let created = 0
    testApp.mock
      .onGet(`application/${APPLICATION_ID}/integrations/`)
      .reply(() => {
        created += 1
        store.dispatch('integration/forceCreate', {
          application: application(),
          integration: {
            id: 100 + created,
            type: 'slack_bot',
            name: `Bot ${created}`,
            order: `${created}`,
          },
        })
        return [200, []]
      })

    expect(
      await store.dispatch('integration/fetch', { application: application() })
    ).toBeNull()
    // It gave up rather than asking forever.
    expect(created).toBe(3)
  })
})
