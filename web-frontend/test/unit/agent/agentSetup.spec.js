import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import {
  SETUP_ACTS_AS,
  SETUP_PERMISSIONS,
  SETUP_START,
  applyAgentSetup,
  newIdentityRoleUid,
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
    actsAs: { kind: SETUP_ACTS_AS.NONE },
    permissions: SETUP_PERMISSIONS.ASK,
    webSearch: false,
    actionTypes: [],
    ...extra,
  })

  const full = setup({
    start: SETUP_START.SCHEDULE,
    actsAs: { kind: SETUP_ACTS_AS.NEW, roleUid: 'BUILDER' },
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
    configurationData = configuration(),
    savedConfiguration = {},
  } = {}) {
    reply('onPost', '/applications/workspace/1/', applicationStatus, {
      id: 10,
      name: 'Deal scout',
      type: 'agent',
      workspace: { id: 1 },
    })
    reply('onGet', '/agent/10/configuration/', 200, configurationData)
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
          run_as_subject_type: 'auth.User',
          run_as_subject_id: 7,
          allowed_tools: ['list_tables', 'create_rows'],
          ask_first_tools: ['create_rows'],
          web_search_enabled: true,
        },
      ],
      [
        'POST',
        '/agent/10/triggers/',
        expect.objectContaining({
          type: 'periodic',
          message: expect.objectContaining({ mode: 'simple' }),
          service: expect.objectContaining({
            interval: 'DAY',
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
      'POST /agent/10/triggers/',
      'POST /agent/10/actions/',
    ])
    expect(requests[3][2]).toEqual({
      instructions: 'Find companies.',
      web_search_enabled: true,
    })
  })

  test('skips and reports the extras the agent cannot have', async () => {
    mockAll({
      configurationData: configuration({
        web_search_available: false,
        available_action_types: [],
      }),
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

  test('reports a web search the chosen tools block', async () => {
    mockAll({ savedConfiguration: { web_search_blocked_by_tools: true } })

    const { notApplied } = await apply(full)

    expect(notApplied).toEqual(['agent.webSearch'])
  })

  test('rejects without other requests when the agent is not created', async () => {
    testApp.dontFailOnErrorResponses()
    mockAll({ applicationStatus: 400 })

    await expect(apply(full)).rejects.toThrow()
    expect(requests.map(([method, url]) => `${method} ${url}`)).toEqual([
      'POST /applications/workspace/1/',
    ])
  })
})
