import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import {
  SETUP_ACTS_AS,
  SETUP_PERMISSIONS,
  SETUP_START,
  SETUP_SUGGESTIONS,
  applyAgentSetup,
  emptyAgentSetup,
  newIdentityRoleUid,
  setupTools,
  suggestionSetup,
  toolsForPermissions,
} from '@baserow/modules/agent/utils/agentSetup'
import { workspace as workspaceData } from './helpers'

const tools = [
  { name: 'list_tables', changes_data: false },
  { name: 'create_rows', changes_data: true },
]

describe('toolsForPermissions', () => {
  test.each([
    [SETUP_PERMISSIONS.READ, ['list_tables'], []],
    [SETUP_PERMISSIONS.ASK, ['list_tables', 'create_rows'], ['create_rows']],
    [SETUP_PERMISSIONS.CHANGE, ['list_tables', 'create_rows'], []],
  ])('%s', (permissions, allowed, askFirst) => {
    expect(toolsForPermissions(tools, permissions)).toEqual({
      allowed_tools: allowed,
      ask_first_tools: askFirst,
    })
  })
})

describe('setupTools', () => {
  const custom = { allowed_tools: ['create_rows'], ask_first_tools: [] }

  test.each([
    [SETUP_PERMISSIONS.CUSTOM, custom],
    [
      SETUP_PERMISSIONS.READ,
      { allowed_tools: ['list_tables'], ask_first_tools: [] },
    ],
  ])('%s', (permissions, expected) => {
    expect(setupTools({ permissions, customTools: custom }, tools)).toEqual(
      expected
    )
  })
})

describe('suggestionSetup', () => {
  const WEEKLY = { interval: 'WEEK', day_of_week: 0 }
  const { CHAT, SCHEDULE } = SETUP_START
  const { READ, ASK } = SETUP_PERMISSIONS

  test.each([
    ['Invest', SCHEDULE, null, ASK, true, []],
    ['Outreach', CHAT, null, READ, true, ['smtp_email']],
    ['Triage', CHAT, null, ASK, false, []],
    ['Summary', SCHEDULE, WEEKLY, READ, false, []],
  ])(
    '%s fills the whole setup',
    (key, start, schedule, permissions, webSearch, actionTypes) => {
      const suggestion = SETUP_SUGGESTIONS.find(
        ({ labelKey }) => labelKey === `agent.setupSuggestion${key}`
      )

      expect(
        suggestionSetup(suggestion, (text) => text, ['smtp_email'])
      ).toEqual({
        name: `agent.setupSuggestion${key}Name`,
        instructions: `agent.setupSuggestion${key}Instructions`,
        start,
        schedule,
        permissions,
        webSearch,
        actionTypes,
      })
    }
  )

  test('leaves out an action the wizard does not offer', () => {
    const outreach = SETUP_SUGGESTIONS.find(
      ({ setup }) => setup.actionTypes.length
    )

    expect(suggestionSetup(outreach, (text) => text, []).actionTypes).toEqual(
      []
    )
  })
})

describe('emptyAgentSetup', () => {
  test.each([
    [
      'the first enabled model',
      { anthropic: [], openai: ['model-one', 'model-two'] },
      { providerType: 'openai', modelIdentifier: 'model-one' },
    ],
    ['no model', {}, { providerType: null, modelIdentifier: null }],
  ])('starts with %s', (_, models, expected) => {
    const workspace = { ai_features: { ai_agent: { models } } }

    expect(emptyAgentSetup('Deal scout', workspace, false)).toMatchObject({
      ...expected,
      reasoningEffort: null,
      permissions: SETUP_PERMISSIONS.ASK,
      customTools: null,
      webSearch: false,
    })
  })
})

describe('newIdentityRoleUid', () => {
  const role = (uid, extra = {}) => ({
    uid,
    isVisible: true,
    isDeactivated: false,
    allowedSubjectTypes: null,
    ...extra,
  })

  test.each([
    ['a Builder role', [role('ADMIN'), role('BUILDER')], 'BUILDER'],
    ['no Builder role', [role('ADMIN'), role('MEMBER')], 'MEMBER'],
    [
      'a Builder role identities cannot have',
      [role('BUILDER', { allowedSubjectTypes: ['baserow_enterprise.Team'] })],
      'MEMBER',
    ],
    [
      'a deactivated Builder role',
      [role('BUILDER', { isDeactivated: true })],
      'MEMBER',
    ],
  ])('with %s', (_, roles, uid) => {
    expect(newIdentityRoleUid({ _: { roles } })).toBe(uid)
  })
})

describe('applyAgentSetup', () => {
  let testApp, workspace, requests

  const configuration = (extra = {}) => ({
    instructions: '',
    available_tools: tools,
    web_search_available: true,
    available_action_types: ['smtp_email'],
    ...extra,
  })

  const setup = (extra = {}) => ({
    name: 'Deal scout',
    instructions: 'Find companies.',
    start: SETUP_START.CHAT,
    schedule: null,
    actsAs: { kind: SETUP_ACTS_AS.NONE },
    permissions: SETUP_PERMISSIONS.ASK,
    customTools: null,
    providerType: null,
    modelIdentifier: null,
    reasoningEffort: null,
    webSearch: false,
    actionTypes: [],
    ...extra,
  })

  const full = setup({
    start: SETUP_START.SCHEDULE,
    schedule: { interval: 'WEEK', day_of_week: 0 },
    actsAs: { kind: SETUP_ACTS_AS.NEW, roleUid: 'BUILDER' },
    providerType: 'openai',
    modelIdentifier: 'model-two',
    reasoningEffort: 'low',
    webSearch: true,
    actionTypes: ['smtp_email'],
  })

  function reply(method, url, status, data) {
    testApp.mock[method](url).reply((config) => {
      requests.push([
        config.method.toUpperCase(),
        config.url,
        config.data ? JSON.parse(config.data) : undefined,
      ])
      return [status, data]
    })
  }

  function mockAll({
    applicationStatus = 200,
    identityStatus = 200,
    configurationStatus = 200,
    configurationData = configuration(),
    savedConfiguration = { web_search_available: true },
  } = {}) {
    reply('onPost', '/applications/workspace/1/', applicationStatus, {
      id: 10,
      name: 'Deal scout',
      type: 'agent',
      workspace: { id: 1 },
    })
    reply(
      'onGet',
      '/agent/10/configuration/',
      configurationStatus,
      configurationData
    )
    reply('onPost', '/identities/workspace/1/', identityStatus, {
      id: 7,
      name: 'Deal scout',
      workspace_id: 1,
    })
    reply('onPatch', '/agent/10/configuration/', 200, savedConfiguration)
    reply('onPost', '/agent/10/triggers/', 200, { id: 1 })
    reply('onPost', '/agent/10/actions/', 200, { id: 2 })
  }

  const apply = (values) =>
    applyAgentSetup(
      {
        store: testApp.store,
        client: testApp.nuxtApp.$client,
        registry: testApp.getRegistry(),
        t: (key) => key,
      },
      workspace,
      values
    )

  const emailName = () =>
    testApp.getRegistry().get('service', 'smtp_email').name

  beforeEach(async () => {
    testApp = new TestApp()
    requests = []
    await testApp.store.dispatch('workspace/forceCreate', clone(workspaceData))
    workspace = testApp.store.getters['workspace/get'](workspaceData.id)
  })

  afterEach(() => testApp.afterEach())

  test('creates the agent, then applies every choice in order', async () => {
    mockAll()

    const { application, notApplied } = await apply(full)

    expect(application.id).toBe(10)
    expect(notApplied).toEqual([])
    expect(requests).toEqual([
      [
        'POST',
        '/applications/workspace/1/',
        { name: 'Deal scout', type: 'agent', init_with_data: true },
      ],
      ['GET', '/agent/10/configuration/', undefined],
      [
        'POST',
        '/identities/workspace/1/',
        { name: 'Deal scout', role_uid: 'BUILDER' },
      ],
      [
        'PATCH',
        '/agent/10/configuration/',
        {
          instructions: 'Find companies.',
          provider_type: 'openai',
          model_identifier: 'model-two',
          reasoning_effort: 'low',
          run_as_subject_type: 'auth.User',
          run_as_subject_id: 7,
          allowed_tools: ['list_tables', 'create_rows'],
          ask_first_tools: ['create_rows'],
        },
      ],
      ['PATCH', '/agent/10/configuration/', { web_search_enabled: true }],
      [
        'POST',
        '/agent/10/triggers/',
        expect.objectContaining({
          type: 'periodic',
          message: expect.objectContaining({ mode: 'simple' }),
          service: expect.objectContaining({
            interval: 'WEEK',
            day_of_week: 0,
            hour: 9,
            minute: 0,
          }),
        }),
      ],
      ['POST', '/agent/10/actions/', { type: 'smtp_email' }],
    ])
  })

  test('sends only the instructions for a chat agent without access or extras', async () => {
    mockAll()

    const { notApplied } = await apply(setup())

    expect(notApplied).toEqual([])
    expect(requests).toEqual([
      [
        'POST',
        '/applications/workspace/1/',
        { name: 'Deal scout', type: 'agent', init_with_data: true },
      ],
      ['GET', '/agent/10/configuration/', undefined],
      [
        'PATCH',
        '/agent/10/configuration/',
        { instructions: 'Find companies.' },
      ],
    ])
  })

  test('goes on without an identity it could not create', async () => {
    testApp.dontFailOnErrorResponses()
    mockAll({ identityStatus: 400 })

    const { notApplied } = await apply(full)

    expect(notApplied).toEqual(['agent.setupActsAs'])
    expect(requests.map(([method, url]) => `${method} ${url}`)).toEqual([
      'POST /applications/workspace/1/',
      'GET /agent/10/configuration/',
      'POST /identities/workspace/1/',
      'PATCH /agent/10/configuration/',
      'PATCH /agent/10/configuration/',
      'POST /agent/10/triggers/',
      'POST /agent/10/actions/',
    ])
    expect(requests[3][2]).toEqual({
      instructions: 'Find companies.',
      provider_type: 'openai',
      model_identifier: 'model-two',
      reasoning_effort: 'low',
    })
  })

  test('sends custom tools as chosen without the configuration', async () => {
    testApp.dontFailOnErrorResponses()
    mockAll({ configurationStatus: 500 })
    const customTools = {
      allowed_tools: ['create_rows'],
      ask_first_tools: [],
    }

    const { notApplied } = await apply(
      setup({
        actsAs: { kind: SETUP_ACTS_AS.EXISTING, id: 7, name: 'Investor' },
        permissions: SETUP_PERMISSIONS.CUSTOM,
        customTools,
      })
    )

    expect(notApplied).toEqual([])
    expect(requests[2][2]).toEqual({
      instructions: 'Find companies.',
      run_as_subject_type: 'auth.User',
      run_as_subject_id: 7,
      ...customTools,
    })
  })

  test('skips and reports the extras the agent cannot have', async () => {
    mockAll({
      configurationData: configuration({ available_action_types: [] }),
      savedConfiguration: { web_search_available: false },
    })

    const { notApplied } = await apply(
      setup({ webSearch: true, actionTypes: ['smtp_email'] })
    )

    expect(notApplied).toEqual(['agent.webSearch', emailName()])
    expect(requests.map(([method, url]) => `${method} ${url}`)).toEqual([
      'POST /applications/workspace/1/',
      'GET /agent/10/configuration/',
      'PATCH /agent/10/configuration/',
    ])
    expect(requests[2][2]).toEqual({ instructions: 'Find companies.' })
  })

  test.each([
    ['turns on', true, [], [{ web_search_enabled: true }]],
    ['reports', false, ['agent.webSearch'], []],
  ])(
    '%s web search from the read configuration when nothing else is saved',
    async (_, available, expected, saves) => {
      mockAll({
        configurationData: configuration({ web_search_available: available }),
        savedConfiguration: { web_search_available: !available },
      })

      const { notApplied } = await apply(
        setup({ instructions: '', webSearch: true })
      )

      expect(notApplied).toEqual(expected)
      expect(requests.slice(2).map(([, , body]) => body)).toEqual(saves)
    }
  )

  test('rejects without other requests when the agent is not created', async () => {
    testApp.dontFailOnErrorResponses()
    mockAll({ applicationStatus: 400 })

    await expect(apply(full)).rejects.toThrow()
    expect(requests.map(([method, url]) => `${method} ${url}`)).toEqual([
      'POST /applications/workspace/1/',
    ])
  })
})
