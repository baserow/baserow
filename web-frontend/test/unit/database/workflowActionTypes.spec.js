import { vi } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { TestApp } from '@baserow/test/helpers/testApp'
import OpenUrlWorkflowActionForm from '@baserow/modules/database/components/field/OpenUrlWorkflowActionForm'

// Read rather than imported: the i18n loader turns an imported locale file
// into compiled message ASTs, which the copy below can't be read off of.
const en = JSON.parse(
  readFileSync(
    resolve(process.cwd(), 'modules/database/locales/en.json'),
    'utf8'
  )
)

describe('databaseWorkflowActionType registry', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('every type is registered', () => {
    const types = testApp._app.$registry.getAll('databaseWorkflowActionType')
    expect(Object.keys(types).sort()).toEqual([
      'http_request',
      'local_baserow_create_row',
      'local_baserow_delete_row',
      'local_baserow_update_row',
      'open_url',
      'slack_write_message',
      'smtp_email',
    ])
  })

  test('open url is offered above the row actions', () => {
    const ordered = testApp._app.$registry.getOrderedList(
      'databaseWorkflowActionType'
    )
    expect(ordered.map((type) => type.getType())).toEqual([
      'open_url',
      'http_request',
      'smtp_email',
      'local_baserow_create_row',
      'local_baserow_update_row',
      'local_baserow_delete_row',
      'slack_write_message',
    ])
  })

  test('each type shows the icon and label the design gives it', () => {
    // Figma "New direction", node 5206:9610. `$t` returns the key here, so
    // the copy is pinned against the locale file separately.
    const registry = testApp._app.$registry
    const expected = {
      open_url: ['iconoir-link', 'databaseWorkflowActionType.openUrl'],
      http_request: ['iconoir-cloud-upload', 'serviceType.coreHTTPRequest'],
      smtp_email: ['iconoir-mail', 'databaseWorkflowActionType.sendEmail'],
      local_baserow_create_row: [
        'iconoir-add-circle',
        'serviceType.localBaserowCreateRow',
      ],
      local_baserow_update_row: [
        'iconoir-edit-pencil',
        'serviceType.localBaserowUpdateRow',
      ],
      local_baserow_delete_row: [
        'iconoir-bin',
        'databaseWorkflowActionType.deleteRow',
      ],
    }
    for (const [type, [icon, label]] of Object.entries(expected)) {
      const actionType = registry.get('databaseWorkflowActionType', type)
      expect([type, actionType.icon]).toEqual([type, icon])
      expect([type, actionType.label]).toEqual([type, label])
      expect(actionType.image).toBeFalsy()
    }
    expect(en.databaseWorkflowActionType.sendEmail).toBe('Send email')
    expect(en.databaseWorkflowActionType.deleteRow).toBe('Delete a row')

    // Slack is the one drawn with its own logo rather than a glyph.
    const slack = registry.get(
      'databaseWorkflowActionType',
      'slack_write_message'
    )
    expect(slack.icon).toBeNull()
    // Vite inlines the asset in tests, so only the format is checkable.
    expect(slack.image).toMatch(/svg/)
    expect(slack.label).toBe('serviceType.slackWriteMessage')
  })

  test('each type resolves a service type with a form component', () => {
    const registry = testApp._app.$registry
    for (const type of [
      'local_baserow_create_row',
      'local_baserow_update_row',
      'local_baserow_delete_row',
    ]) {
      const actionType = registry.get('databaseWorkflowActionType', type)
      expect(actionType.serviceType).toBeTruthy()
      expect(actionType.serviceType.formComponent).toBeTruthy()
      expect(actionType.label).toBeTruthy()
      expect(actionType.icon || actionType.image).toBeTruthy()
    }
  })

  test('each type resolves the exact service type it declares', () => {
    const registry = testApp._app.$registry
    const cases = [
      ['local_baserow_create_row', 'local_baserow_create_row'],
      ['local_baserow_update_row', 'local_baserow_update_row'],
      ['local_baserow_delete_row', 'local_baserow_delete_row'],
    ]
    for (const [actionType, serviceType] of cases) {
      expect(
        registry.get('databaseWorkflowActionType', actionType).serviceType
      ).toBe(registry.get('service', serviceType))
    }
  })
})

describe('OpenUrlWorkflowActionType', () => {
  let testApp = null
  let actionType = null
  let openSpy = null
  let dispatchSpy = null
  let originalLocation = null

  const row = { id: 1, field_1: 'example.com' }
  const fields = [{ id: 1, type: 'text', name: 'Domain' }]

  beforeAll(() => {
    testApp = new TestApp()
    actionType = testApp._app.$registry.get(
      'databaseWorkflowActionType',
      'open_url'
    )
  })

  beforeEach(() => {
    openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    dispatchSpy = vi.spyOn(testApp._app.$store, 'dispatch')
    originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
      configurable: true,
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
      configurable: true,
    })
    vi.restoreAllMocks()
    testApp.afterEach()
  })

  const execute = (workflowAction) =>
    actionType.execute({
      workflowAction,
      applicationContext: { row, fields },
    })

  test('it renders its own form, not a service one', () => {
    expect(actionType.form).toBe(OpenUrlWorkflowActionForm)
    expect(actionType.icon).toBe('iconoir-link')
    expect(actionType.label).toBeTruthy()
  })

  test('the same tab target navigates the current page', async () => {
    await execute({
      type: 'open_url',
      url: { formula: "concat('https://', get('fields.field_1'))" },
      target: 'self',
    })

    expect(window.location.href).toBe('https://example.com')
    expect(openSpy).not.toHaveBeenCalled()
  })

  test('the new tab target opens a new window', async () => {
    await execute({
      type: 'open_url',
      url: { formula: "'https://example.com'" },
      target: 'blank',
    })

    expect(openSpy).toHaveBeenCalledWith(
      'https://example.com',
      '_blank',
      'noopener,noreferrer'
    )
    expect(window.location.href).toBe('')
  })

  test('whitespace in a resolved url is encoded', async () => {
    await execute({
      type: 'open_url',
      url: { formula: "'https://example.com/a b'" },
      target: 'self',
    })

    expect(window.location.href).toBe('https://example.com/a%20b')
  })

  // The `row` provider returns raw values and is only for action arguments,
  // so a URL formula must never be able to reach it (ADR 006 section 4).
  test('the url resolves against the fields provider only', async () => {
    await execute({
      type: 'open_url',
      url: { formula: "get('row.field_1')" },
      target: 'self',
    })

    expect(window.location.href).toBe('')
    expect(dispatchSpy).toHaveBeenCalledWith(
      'toast/error',
      expect.objectContaining({
        title: 'openUrlWorkflowAction.invalidUrlTitle',
      })
    )
  })

  test('the clicked row id is reachable for a url', async () => {
    await execute({
      type: 'open_url',
      url: { formula: "concat('https://example.com/?id=', get('fields.id'))" },
      target: 'self',
    })

    expect(window.location.href).toBe('https://example.com/?id=1')
  })

  test('a url pointing at a missing field raises a toast instead of throwing', async () => {
    // Resolving to `false` rather than throwing: the caller stops the client
    // actions after this one instead of handling a rejection.
    await expect(
      execute({
        type: 'open_url',
        url: { formula: "get('fields.field_404')" },
        target: 'blank',
      })
    ).resolves.toBe(false)

    expect(openSpy).not.toHaveBeenCalled()
    expect(dispatchSpy).toHaveBeenCalledWith(
      'toast/error',
      expect.objectContaining({
        title: 'openUrlWorkflowAction.invalidUrlTitle',
      })
    )
  })

  test('a javascript url is refused', async () => {
    await execute({
      type: 'open_url',
      url: { formula: "'javascript:alert(1)'" },
      target: 'self',
    })

    expect(window.location.href).toBe('')
    expect(dispatchSpy).toHaveBeenCalledWith(
      'toast/error',
      expect.objectContaining({
        title: 'openUrlWorkflowAction.invalidUrlTitle',
      })
    )
  })

  // A previous action's result comes back raw, so a single select, link row or
  // file resolves to an object. Stringified it would build a URL out of JSON.
  const withResult = (data) => ({
    row,
    fields,
    previousActionResults: {
      7: { data, fieldNames: { field_9: 'Choice' } },
    },
  })

  const executeWith = (workflowAction, applicationContext) =>
    actionType.execute({ workflowAction, applicationContext })

  test('a composite value is refused rather than stringified into a url', async () => {
    await executeWith(
      {
        type: 'open_url',
        url: {
          formula:
            "concat('https://example.com/', get('previous_action.7.field_9'))",
        },
        target: 'self',
      },
      withResult({ id: 3, Choice: { id: 1, value: 'value', color: 'blue' } })
    )

    expect(window.location.href).toBe('')
    expect(dispatchSpy).toHaveBeenCalledWith(
      'toast/error',
      expect.objectContaining({
        title: 'openUrlWorkflowAction.invalidUrlTitle',
      })
    )
  })

  test('a list value is refused too', async () => {
    // A link row or a multiple select.
    await executeWith(
      {
        type: 'open_url',
        url: { formula: "get('previous_action.7.field_9')" },
        target: 'blank',
      },
      withResult({ id: 3, Choice: [{ id: 1, value: 'row' }] })
    )

    expect(openSpy).not.toHaveBeenCalled()
    expect(dispatchSpy).toHaveBeenCalledWith(
      'toast/error',
      expect.objectContaining({
        title: 'openUrlWorkflowAction.invalidUrlTitle',
      })
    )
  })

  test('a scalar from a previous action still resolves', async () => {
    await executeWith(
      {
        type: 'open_url',
        url: {
          formula:
            "concat('https://example.com/', get('previous_action.7.field_9'))",
        },
        target: 'self',
      },
      withResult({ id: 3, Choice: 'plain' })
    )

    expect(window.location.href).toBe('https://example.com/plain')
  })

  test('a path reaching inside a composite still resolves', async () => {
    // Only the leaf reaches the URL, so a deeper path is not a composite.
    await executeWith(
      {
        type: 'open_url',
        url: {
          formula:
            "concat('https://example.com/', get('previous_action.7.field_9.value'))",
        },
        target: 'self',
      },
      withResult({ id: 3, Choice: { id: 1, value: 'value', color: 'blue' } })
    )

    expect(window.location.href).toBe('https://example.com/value')
  })

  test('an empty formula raises a toast rather than navigating', async () => {
    await execute({ type: 'open_url', url: { formula: '' }, target: 'self' })

    expect(window.location.href).toBe('')
    expect(dispatchSpy).toHaveBeenCalledWith(
      'toast/error',
      expect.objectContaining({
        title: 'openUrlWorkflowAction.invalidUrlTitle',
      })
    )
  })
})

describe('external database workflow action types', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const typeFor = (type) =>
    testApp._app.$registry.get('databaseWorkflowActionType', type)

  test('they describe themselves from the service, not from a table', () => {
    const actionType = typeFor('http_request')
    const schema = {
      type: 'object',
      title: 'HTTPRequest12Schema',
      properties: { status_code: { type: 'number' } },
    }

    expect(actionType.getDataSchema({}, { service: { schema } })).toEqual({
      ...schema,
      // The service names its schema for itself. The explorer shows the
      // action's own label, the way every other action type does.
      title: actionType.label,
    })
  })

  test('an action nothing has clicked yet still offers what never changes', () => {
    const actionType = typeFor('http_request')

    // A request always answers with a status code, a raw body and headers,
    // whatever the endpoint replies. Offering nothing at all would leave a
    // freshly added action out of the explorer until the field is saved and
    // opened again, so the action after it could point at nothing.
    for (const workflowAction of [{ service: {} }, {}]) {
      const schema = actionType.getDataSchema({}, workflowAction)
      expect(Object.keys(schema.properties).sort()).toEqual([
        'headers',
        'raw_body',
        'status_code',
      ])
      // Only a real answer can say what is in the body.
      expect(schema.properties.body).toBeUndefined()
      expect(schema.title).toBe(actionType.label)
    }
  })

  test('an unsaved email already says what it will answer with', () => {
    const actionType = typeFor('smtp_email')

    // An email answers with whether it went out and nothing else, so the
    // action after it can read that before anything is saved.
    for (const workflowAction of [{ service: {} }, {}]) {
      const schema = actionType.getDataSchema({}, workflowAction)
      expect(Object.keys(schema.properties)).toEqual(['success'])
      expect(schema.properties.success.type).toBe('boolean')
      expect(schema.title).toBe(actionType.label)
    }
  })

  test('a saved email is described by its own service', () => {
    const actionType = typeFor('smtp_email')
    const schema = {
      type: 'object',
      title: 'SMTPEmail12Schema',
      properties: { success: { type: 'boolean', title: 'Success' } },
    }

    expect(actionType.getDataSchema({}, { service: { schema } })).toEqual({
      ...schema,
      title: actionType.label,
    })
  })

  test('a table fetch cannot describe them either', () => {
    const actionType = typeFor('http_request')
    const applicationContext = { tableFields: { 1: [{ id: 2, type: 'text' }] } }

    // A row action would build its schema from these; an HTTP one must not.
    const schema = actionType.getDataSchema(applicationContext, {
      service: { table_id: 1 },
    })
    expect(schema.properties.field_2).toBeUndefined()
  })

  test('both can be read by a later action', () => {
    expect(typeFor('http_request').producesResult).toBe(true)
    expect(typeFor('smtp_email').producesResult).toBe(true)
  })

  test('neither offers field mappings', () => {
    expect(typeFor('http_request').mapsFields).toBe(false)
    expect(typeFor('smtp_email').mapsFields).toBe(false)
  })

  test('email keeps the integration branch out of its form', () => {
    // A button's actions carry no integration, so the dropdown could never be
    // filled and unchecking the box would build a service that fails on click.
    expect(typeFor('smtp_email').serviceFormProps).toEqual({
      allowIntegration: false,
    })
    expect(typeFor('smtp_email').getNewActionValues()).toEqual({
      service: { use_instance_smtp_settings: true },
    })
  })

  test('http asks for no extra form props', () => {
    expect(typeFor('http_request').serviceFormProps).toEqual({})
  })

  test('an unsaved slack message already says what it will answer with', () => {
    const actionType = typeFor('slack_write_message')

    // Slack answers with the same three things whatever the message, so the
    // action after it can point at the message timestamp before saving. Under
    // `data`, which is where the dispatch puts them and what the backend's
    // `generate_schema` describes.
    for (const workflowAction of [{ service: {} }, {}]) {
      const schema = actionType.getDataSchema({}, workflowAction)
      expect(Object.keys(schema.properties)).toEqual(['data'])
      const answer = schema.properties.data.properties
      expect(Object.keys(answer)).toEqual(['ok', 'channel', 'ts'])
      expect(answer.ok.type).toBe('boolean')
      expect(answer.ts.type).toBe('string')
      expect(schema.title).toBe(actionType.label)
    }
  })

  test('slack keeps the integration dropdown, the others do not need one', () => {
    // A Slack bot is the credential the action sends through, so its form
    // must offer the dropdown and the editor must fetch what it can list.
    expect(typeFor('slack_write_message').serviceFormProps).toEqual({})
    expect(typeFor('slack_write_message').needsIntegration).toBe(true)
    expect(typeFor('smtp_email').needsIntegration).toBe(false)
    expect(typeFor('http_request').needsIntegration).toBe(false)
    expect(typeFor('local_baserow_create_row').needsIntegration).toBe(false)
  })

  test('each resolves the shared service type and its form', () => {
    for (const [actionType, serviceType] of [
      ['http_request', 'http_request'],
      ['smtp_email', 'smtp_email'],
      ['slack_write_message', 'slack_write_message'],
    ]) {
      const type = typeFor(actionType)
      expect(type.serviceType.getType()).toBe(serviceType)
      expect(type.serviceType.formComponent).toBeTruthy()
    }
  })
})

describe('CoreSMTPEmailWorkflowActionType', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const emailType = () =>
    testApp._app.$registry.get('databaseWorkflowActionType', 'smtp_email')

  const withInstanceSmtp = (instanceSmtp) =>
    testApp.store.commit('settings/SET_SETTINGS', {
      instance_smtp: instanceSmtp,
    })

  // What the action list passes: the base type only asks about deactivation
  // when it knows the workspace.
  const context = { workspace: { id: 1 } }

  test('an instance that cannot send is said so before the action is saved', () => {
    withInstanceSmtp({ available: false, unavailable_reason: 'no_server' })

    // An action being configured has no service yet, so the reason cannot
    // come from one.
    const action = { id: 1, type: 'smtp_email' }

    // `$t` returns the key in the test env, so the copy is pinned separately.
    expect(emailType().getErrorMessage(action, context)).toBe(
      'databaseWorkflowActionType.noInstanceSmtp'
    )
    expect(en.databaseWorkflowActionType.noInstanceSmtp).toContain(
      'no SMTP server configured'
    )
  })

  test('sending turned off by an administrator says that instead', () => {
    withInstanceSmtp({ available: false, unavailable_reason: 'turned_off' })

    expect(
      emailType().getErrorMessage({ id: 1, type: 'smtp_email' }, context)
    ).toBe('databaseWorkflowActionType.instanceSmtpTurnedOff')
    expect(en.databaseWorkflowActionType.instanceSmtpTurnedOff).toContain(
      'turned off'
    )
  })

  test('an instance that can send says nothing', () => {
    withInstanceSmtp({ available: true, unavailable_reason: null })

    expect(
      emailType().getErrorMessage({ id: 1, type: 'smtp_email' }, context)
    ).toBeNull()
  })

  test('an installation older than the flag is left to the click', () => {
    testApp.store.commit('settings/SET_SETTINGS', {})

    expect(
      emailType().getErrorMessage({ id: 1, type: 'smtp_email' }, context)
    ).toBeNull()
  })
})
