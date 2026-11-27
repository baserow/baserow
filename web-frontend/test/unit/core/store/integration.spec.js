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

  test('an update merges the response, without storing the credential', async () => {
    await store.dispatch('integration/forceCreate', {
      application: application(),
      integration: {
        id: 11,
        type: 'smtp',
        name: 'Mailer',
        order: '1',
        host: 'smtp.example.com',
        has_password: false,
      },
    })

    testApp.mock.onPatch('integration/11/').reply(200, {
      id: 11,
      type: 'smtp',
      name: 'Mailer',
      order: '1',
      host: 'smtp.example.com',
      has_password: true,
    })

    await store.dispatch('integration/update', {
      application: application(),
      integrationId: 11,
      values: { password: 'secret' },
    })

    const stored = application().integrations.find((i) => i.id === 11)
    expect(stored.has_password).toBe(true)
    expect(stored.password).toBeUndefined()
  })

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

  test('update merges server-generated fields into the integration', async () => {
    const integration = {
      id: 1,
      type: 'local_baserow',
      name: 'Local Baserow',
      authorized_subject: {
        id: 2,
        type: 'auth.User',
        username: 'user@example.com',
      },
      context_data: { databases: [] },
    }
    const application = { id: 10, integrations: [integration] }
    const updatedIntegration = {
      ...integration,
      authorized_subject: {
        id: 3,
        type: 'auth.User',
        user_type: 'identity',
        name: 'Writer identity',
      },
      context_data: { databases: [{ id: 4, name: 'Identity database' }] },
    }
    testApp.mock.onPatch('/integration/1/').reply(200, updatedIntegration)

    await testApp.store.dispatch('integration/update', {
      application,
      integrationId: integration.id,
      values: {
        authorized_subject_id: 3,
        authorized_subject_type: 'auth.User',
      },
    })

    expect(application.integrations).toEqual([updatedIntegration])
  })
})

describe('workspace integrations in the integration store', () => {
  const WORKSPACE_ID = 1
  const SHARED_APPLICATION = {
    id: 99,
    name: '__shared__',
    type: 'shared',
    order: 0,
    workspace: { id: WORKSPACE_ID },
  }
  const database = (id, workspaceId = WORKSPACE_ID) => ({
    id,
    name: `Database ${id}`,
    type: 'database',
    workspace: { id: workspaceId },
    tables: [],
  })
  const integration = (id, applicationId, name) => ({
    id,
    application_id: applicationId,
    type: 'smtp',
    name,
    order: `${id}`,
  })

  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('workspace/forceCreate', {
      id: WORKSPACE_ID,
      name: 'Acme',
    })
    await store.dispatch('application/forceCreate', database(100))
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const get = (id) => store.getters['application/get'](id)
  const names = (integrations) => integrations.map(({ name }) => name)
  const usable = (id) =>
    names(store.getters['integration/getUsableIntegrations'](get(id)))
  const fetchOnce = (id) =>
    store.dispatch('integration/fetchWorkspaceIntegrationsOnce', {
      application: get(id),
    })

  test('an application uses its own integrations, then the workspace ones', async () => {
    await store.dispatch('application/forceCreate', database(200, 2))
    await store.dispatch('integration/forceCreate', {
      application: get(100),
      integration: integration(1, 100, 'Own'),
    })
    await store.dispatch('application/forceCreate', { ...SHARED_APPLICATION })
    await store.dispatch('integration/forceCreate', {
      application: get(SHARED_APPLICATION.id),
      integration: integration(2, SHARED_APPLICATION.id, 'Team'),
    })

    expect(usable(100)).toEqual(['Own', 'Team'])
    // A service using a workspace integration finds it.
    expect(
      store.getters['integration/getIntegrationById'](get(100), 2)
    ).toMatchObject({ name: 'Team' })
    // A settings page lists the application's own only.
    const own = store.getters['integration/getIntegrations'](get(100))
    expect(names(own)).toEqual(['Own'])
    // The shared application owns them, so they aren't listed twice.
    expect(usable(SHARED_APPLICATION.id)).toEqual(['Team'])
    // Another workspace has none of them.
    expect(usable(200)).toEqual([])
  })

  const workspaceIntegrations = (
    integrations,
    sharedApplication,
    integrationTypes = ['local_baserow', 'smtp']
  ) => ({
    shared_application: sharedApplication,
    integration_types: integrationTypes,
    integrations,
  })

  test('the workspace integrations are fetched once per application', async () => {
    await store.dispatch('application/forceCreate', database(101))
    // The store doesn't have the shared application, like for a user with a
    // role on some applications only, whose application listing leaves it out.
    for (const id of [100, 101]) {
      testApp.mock
        .onGet(`application/${id}/workspace-integrations/`)
        .reply(
          200,
          workspaceIntegrations(
            [integration(2, SHARED_APPLICATION.id, 'Team')],
            SHARED_APPLICATION
          )
        )
    }

    expect(names(await fetchOnce(100))).toEqual(['Team'])
    expect(names(await fetchOnce(100))).toEqual(['Team'])
    expect(names(await fetchOnce(101))).toEqual(['Team'])

    expect(testApp.mock.history.get.map(({ url }) => url)).toEqual([
      'application/100/workspace-integrations/',
      'application/101/workspace-integrations/',
    ])
    expect(
      store.getters['application/getSharedApplication']({ id: WORKSPACE_ID })
    ).toMatchObject({ id: SHARED_APPLICATION.id })
    expect(usable(101)).toEqual(['Team'])
  })

  test('an application only replaces the workspace integrations of its types', async () => {
    // The backend sends a database the types its button actions carry, and an
    // application builder every type.
    await store.dispatch('application/forceCreate', database(101))
    const team = { ...integration(2, SHARED_APPLICATION.id, 'Team') }
    const rows = {
      ...integration(3, SHARED_APPLICATION.id, 'Rows'),
      type: 'local_baserow',
    }
    testApp.mock
      .onGet('application/100/workspace-integrations/')
      .reply(
        200,
        workspaceIntegrations([team, rows], SHARED_APPLICATION, [
          'local_baserow',
          'smtp',
        ])
      )
    testApp.mock
      .onGet('application/101/workspace-integrations/')
      .reply(
        200,
        workspaceIntegrations(
          [{ ...team, name: 'Team, renamed' }],
          SHARED_APPLICATION,
          ['smtp']
        )
      )

    await fetchOnce(100)
    expect(names(await fetchOnce(101))).toEqual(['Team, renamed'])

    // The Local Baserow one the database wasn't sent is still there for the
    // other application, which doesn't fetch them again.
    expect(usable(100)).toEqual(['Rows', 'Team, renamed'])
    expect(names(await fetchOnce(100))).toEqual(['Rows', 'Team, renamed'])
    // Only what the database can use is returned for it.
    expect(names(await fetchOnce(101))).toEqual(['Team, renamed'])
    expect(testApp.mock.history.get).toHaveLength(2)
  })

  test('nothing is loaded for a workspace without shared application', async () => {
    testApp.mock
      .onGet('application/100/workspace-integrations/')
      .reply(200, workspaceIntegrations([], null))

    expect(await fetchOnce(100)).toEqual([])
    expect(
      store.getters['application/getSharedApplication']({ id: WORKSPACE_ID })
    ).toBeUndefined()
  })

  test('a fetch that gave up is asked again, one that loaded is not', async () => {
    await store.dispatch('application/forceCreate', { ...SHARED_APPLICATION })
    let settled = false
    let attempts = 0
    testApp.mock.onGet('application/100/workspace-integrations/').reply(() => {
      attempts += 1
      if (!settled) {
        // Written to during every attempt, so no answer is ever current.
        store.dispatch('integration/forceCreate', {
          application: get(SHARED_APPLICATION.id),
          integration: integration(attempts, SHARED_APPLICATION.id, 'New'),
        })
      }
      return [
        200,
        workspaceIntegrations(
          [integration(2, SHARED_APPLICATION.id, 'Team')],
          SHARED_APPLICATION
        ),
      ]
    })

    expect(await fetchOnce(100)).toBeNull()
    settled = true
    expect(names(await fetchOnce(100))).toEqual(['Team'])
    const attemptsWhenLoaded = attempts
    expect(names(await fetchOnce(100))).toEqual(['Team'])

    expect(attempts).toBe(attemptsWhenLoaded)
  })

  test('nothing is fetched for a workspace the user is not a member of', async () => {
    // Like the workspace of a template preview.
    await store.dispatch('application/forceCreate', database(200, 2))

    expect(await fetchOnce(200)).toEqual([])
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('nothing is fetched for a user who cannot list them', async () => {
    // Like a user with a role on other applications of the workspace only.
    const app = store.app
    const asked = []
    store.app = Object.create(app, {
      $hasPermission: {
        value: (...args) => {
          asked.push(args)
          return false
        },
      },
    })
    try {
      expect(await fetchOnce(100)).toEqual([])
    } finally {
      store.app = app
    }

    // Asked about the application they're used from, not the workspace.
    expect(asked).toEqual([
      [
        'application.list_integrations',
        expect.objectContaining({ id: 100 }),
        WORKSPACE_ID,
      ],
    ])
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  const WORKSPACE_INTEGRATIONS_URL = 'application/100/workspace-integrations/'
  const fetchForced = (id) =>
    store.dispatch('integration/fetchWorkspaceIntegrations', {
      application: get(id),
      force: true,
    })
  // A Local Baserow workspace integration, with the tables the backend found
  // it can reach when it sent it.
  const localBaserow = (tables) => ({
    ...integration(2, SHARED_APPLICATION.id, 'Team'),
    type: 'local_baserow',
    context_data: {
      databases: [
        {
          id: 7,
          name: 'Sales',
          tables: tables.map((name, index) => ({ id: index + 1, name })),
          views: [],
        },
      ],
    },
  })
  const reachableTables = (id) =>
    store.getters['integration/getUsableIntegrations'](get(id)).flatMap(
      ({ context_data: contextData }) =>
        contextData.databases.flatMap(({ tables }) =>
          tables.map(({ name }) => name)
        )
    )
  const requested = (url) =>
    testApp.mock.history.get.filter((request) => request.url === url)

  test('a forced fetch loads the workspace integrations again', async () => {
    testApp.mock
      .onGet(WORKSPACE_INTEGRATIONS_URL)
      .replyOnce(
        200,
        workspaceIntegrations([localBaserow(['Leads'])], SHARED_APPLICATION)
      )
    // A table created since, which no realtime event about the integration
    // tells the store.
    testApp.mock
      .onGet(WORKSPACE_INTEGRATIONS_URL)
      .replyOnce(
        200,
        workspaceIntegrations(
          [localBaserow(['Leads', 'Deals'])],
          SHARED_APPLICATION
        )
      )

    await fetchOnce(100)
    expect(reachableTables(100)).toEqual(['Leads'])

    expect(names(await fetchForced(100))).toEqual(['Team'])

    expect(requested(WORKSPACE_INTEGRATIONS_URL)).toHaveLength(2)
    expect(reachableTables(100)).toEqual(['Leads', 'Deals'])
  })

  test('loading once fetches nothing after a forced fetch', async () => {
    testApp.mock
      .onGet(WORKSPACE_INTEGRATIONS_URL)
      .replyOnce(
        200,
        workspaceIntegrations([localBaserow(['Leads'])], SHARED_APPLICATION)
      )

    await fetchForced(100)
    expect(names(await fetchOnce(100))).toEqual(['Team'])

    expect(requested(WORKSPACE_INTEGRATIONS_URL)).toHaveLength(1)
  })

  test('a forced fetch that gave up keeps the list it would have replaced', async () => {
    testApp.mock
      .onGet(WORKSPACE_INTEGRATIONS_URL)
      .replyOnce(
        200,
        workspaceIntegrations([localBaserow(['Leads'])], SHARED_APPLICATION)
      )
    await fetchOnce(100)
    const shared = get(SHARED_APPLICATION.id)
    testApp.mock.onGet(WORKSPACE_INTEGRATIONS_URL).reply(() => {
      // Renamed through a realtime event during every attempt, so no answer
      // is ever current.
      store.dispatch('integration/forceUpdate', {
        application: shared,
        integration: store.getters['integration/getIntegrations'](shared)[0],
        values: { name: 'Renamed' },
      })
      return [
        200,
        workspaceIntegrations(
          [localBaserow(['Leads', 'Deals'])],
          SHARED_APPLICATION
        ),
      ]
    })

    expect(await fetchForced(100)).toBeNull()

    expect(usable(100)).toEqual(['Renamed'])
    expect(reachableTables(100)).toEqual(['Leads'])
    // Still loaded, so loading once doesn't ask again.
    const requests = testApp.mock.history.get.length
    expect(names(await fetchOnce(100))).toEqual(['Renamed'])
    expect(testApp.mock.history.get).toHaveLength(requests)
  })

  const OWN_INTEGRATIONS_URL = 'application/100/integrations/'
  const fetchUsable = (id) =>
    store.dispatch('integration/fetchUsable', { application: get(id) })

  test('every integration an application can use is fetched again', async () => {
    testApp.mock
      .onGet(OWN_INTEGRATIONS_URL)
      .reply(200, [integration(1, 100, 'Own')])
    testApp.mock
      .onGet(WORKSPACE_INTEGRATIONS_URL)
      .reply(
        200,
        workspaceIntegrations(
          [integration(2, SHARED_APPLICATION.id, 'Team')],
          SHARED_APPLICATION
        )
      )

    expect(names(await fetchUsable(100))).toEqual(['Own', 'Team'])
    expect(names(await fetchUsable(100))).toEqual(['Own', 'Team'])

    expect(requested(OWN_INTEGRATIONS_URL)).toHaveLength(2)
    expect(requested(WORKSPACE_INTEGRATIONS_URL)).toHaveLength(2)
    expect(usable(100)).toEqual(['Own', 'Team'])
  })

  test.each([
    ['its own', OWN_INTEGRATIONS_URL, 100],
    ['the workspace ones', WORKSPACE_INTEGRATIONS_URL, SHARED_APPLICATION.id],
  ])(
    'nothing usable is returned when %s keep changing under the fetch',
    async (_, changingUrl, changingApplicationId) => {
      await store.dispatch('application/forceCreate', { ...SHARED_APPLICATION })
      let created = 0
      const answer = (url, body) =>
        testApp.mock.onGet(url).reply(() => {
          if (url === changingUrl) {
            // Created through a realtime event during every attempt, so no
            // answer is ever current.
            created += 1
            store.dispatch('integration/forceCreate', {
              application: get(changingApplicationId),
              integration: integration(
                100 + created,
                changingApplicationId,
                'New'
              ),
            })
          }
          return [200, body]
        })
      answer(OWN_INTEGRATIONS_URL, [integration(1, 100, 'Own')])
      answer(
        WORKSPACE_INTEGRATIONS_URL,
        workspaceIntegrations(
          [integration(2, SHARED_APPLICATION.id, 'Team')],
          SHARED_APPLICATION
        )
      )

      expect(await fetchUsable(100)).toBeNull()
    }
  )

  const own = (id) => store.getters['integration/getIntegrations'](get(id))
  const generation = (id) => store.getters['integration/getGeneration'](get(id))
  const moveToShared = (integrationId) =>
    store.dispatch('integration/moveToApplication', {
      application: get(100),
      applicationDest: get(SHARED_APPLICATION.id),
      integrationId,
    })

  test('a promotion moves the integration once the backend accepted it', async () => {
    await store.dispatch('application/forceCreate', { ...SHARED_APPLICATION })
    await store.dispatch('integration/forceCreate', {
      application: get(100),
      integration: {
        ...integration(1, 100, 'Rows'),
        type: 'local_baserow',
        authorized_subject_id: 5,
      },
    })
    await store.dispatch('integration/forceCreate', {
      application: get(SHARED_APPLICATION.id),
      integration: integration(2, SHARED_APPLICATION.id, 'Team'),
    })
    const generations = [generation(100), generation(SHARED_APPLICATION.id)]
    // The backend authorizes it as the user promoting it.
    const response = held({
      ...integration(1, SHARED_APPLICATION.id, 'Rows'),
      type: 'local_baserow',
      authorized_subject_id: 6,
    })
    testApp.mock.onPatch('integration/1/').replyOnce(response.reply)

    const moving = moveToShared(1)
    await flushPromises()

    // Nothing moves before the backend accepted it.
    expect(names(own(100))).toEqual(['Rows'])
    expect(own(100)[0].application_id).toBe(100)
    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      application_id: SHARED_APPLICATION.id,
    })

    response.release()
    await moving

    expect(own(100)).toEqual([])
    // Last, where the backend orders it, with the values the move changed.
    expect(own(SHARED_APPLICATION.id)).toMatchObject([
      { id: 2 },
      {
        id: 1,
        application_id: SHARED_APPLICATION.id,
        authorized_subject_id: 6,
      },
    ])
    // So the settings pages listing either list refresh.
    expect(generation(100)).toBeGreaterThan(generations[0])
    expect(generation(SHARED_APPLICATION.id)).toBeGreaterThan(generations[1])
    // The application still uses it, now as a workspace integration.
    expect(usable(100)).toEqual(['Team', 'Rows'])
  })

  test('a refused promotion leaves the integration where it was', async () => {
    testApp.dontFailOnErrorResponses()
    await store.dispatch('application/forceCreate', { ...SHARED_APPLICATION })
    await store.dispatch('integration/forceCreate', {
      application: get(100),
      integration: integration(1, 100, 'Mailer'),
    })
    testApp.mock.onPatch('integration/1/').replyOnce(401, {
      error: 'ERROR_PERMISSION_DENIED',
      detail: 'Permission denied',
    })

    await expect(moveToShared(1)).rejects.toThrow()

    expect(own(100)).toMatchObject([{ id: 1, application_id: 100 }])
    expect(own(SHARED_APPLICATION.id)).toEqual([])
  })
})
