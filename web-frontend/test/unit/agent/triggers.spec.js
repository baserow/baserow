import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import moment from '@baserow/modules/core/moment'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import AgentWhenItRunsSection from '@baserow/modules/agent/components/configuration/AgentWhenItRunsSection'
import AgentTriggerMessageInput from '@baserow/modules/agent/components/configuration/AgentTriggerMessageInput'
import AgentTriggerPicker from '@baserow/modules/agent/components/configuration/AgentTriggerPicker'
import { defaultTriggerMessage } from '@baserow/modules/agent/utils/triggers'
import { CorePeriodicTriggerServiceType } from '@baserow/modules/integrations/core/serviceTypes'
import { LocalBaserowRowsCreatedTriggerServiceType } from '@baserow/modules/integrations/localBaserow/serviceTypes'
import agentLocale from '@baserow/modules/agent/locales/en.json'
import integrationsLocale from '@baserow/modules/integrations/locales/en.json'
import {
  agentData,
  choose,
  completeConfiguration,
  deferredReply,
  periodicTrigger,
  useFakeTimers,
  workspace,
} from './helpers'

const rowsSchema = {
  type: 'array',
  title: 'Table31Schema',
  items: {
    type: 'object',
    properties: {
      id: { type: 'number', title: 'Id' },
      field_1: { type: 'string', title: 'Name' },
    },
  },
}

const rowsTrigger = (extra = {}) => ({
  id: 2,
  type: 'local_baserow_rows_created',
  name: '',
  enabled: true,
  message: { formula: "'New orders'", mode: 'simple', version: '0.1' },
  service: {
    id: 7,
    type: 'local_baserow_rows_created',
    table_id: 31,
    integration_id: null,
    schema: rowsSchema,
  },
  on_overlap: 'wait',
  batch_size: 20,
  last_fired_on: null,
  last_skipped_on: null,
  last_skipped_reason: '',
  ...extra,
})

const databases = [
  {
    id: 3,
    name: 'Sales',
    tables: [
      {
        id: 31,
        database_id: 3,
        name: 'Orders',
        is_data_sync: false,
        is_two_way_data_sync: false,
      },
    ],
    views: [],
  },
]

const triggerTypeOf = (type) =>
  type.startsWith('local_baserow_')
    ? { type, form_choices: { databases }, default_on_overlap: 'wait' }
    : { type, form_choices: null, default_on_overlap: 'skip' }

const activeRunAs = {
  run_as: {
    type: 'core.Agent',
    id: 4,
    name: 'Reader',
    trashed: false,
    status: 'active',
  },
}

const DEFAULT_ROWS_MESSAGE = {
  formula:
    "concat(get('trigger.count'), ' rows were created in ', get('trigger.table'), ': ', get('trigger.rows'))",
  mode: 'simple',
  version: '0.1',
}

const patches = (testApp) =>
  testApp.mock.history.patch.map(({ url, data }) => [url, JSON.parse(data)])

describe('Agent triggers', () => {
  let testApp, agent

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', clone(workspace))
    agent = await testApp.store.dispatch(
      'application/forceCreate',
      clone(agentData)
    )
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.useRealTimers()
  })

  // A test mocks the trigger types before mounting to answer differently first.
  const mountSection = (
    triggers,
    availableTypes = ['periodic'],
    editable = true,
    maxQueuedTriggerRuns = 10,
    configuration = {}
  ) => {
    testApp.mock.onGet('/agent/10/triggers/').reply(200, triggers)
    testApp.mock
      .onGet('/agent/10/trigger-types/')
      .reply(200, availableTypes.map(triggerTypeOf))
    return testApp.mount(AgentWhenItRunsSection, {
      props: {
        configuration: completeConfiguration({
          available_trigger_types: availableTypes,
          max_queued_trigger_runs: maxQueuedTriggerRuns,
          max_parallel_trigger_runs: 5,
          ...configuration,
        }),
        editable,
      },
      global: { provide: { agentApplication: ref(agent) } },
    })
  }

  test('hosts the trigger type form on the card and saves service values after the debounce', async () => {
    useFakeTimers()
    testApp.mock.onPatch('/agent/10/triggers/1/').reply((config) => {
      const saved = periodicTrigger()
      const body = JSON.parse(config.data)
      return [200, { ...saved, service: { ...saved.service, ...body.service } }]
    })
    const wrapper = await mountSection([periodicTrigger()])
    const card = wrapper.get('.agent-trigger-card')

    expect(card.get('.agent-trigger-card__name').text()).toBe(
      'serviceType.corePeriodicNameHour'
    )
    expect(
      card.findComponent({ name: 'CorePeriodicTriggerServiceForm' }).exists()
    ).toBe(true)
    expect(card.find('.agent-trigger-card__status').exists()).toBe(false)
    expect(patches(testApp)).toEqual([])

    await choose(card.get('.dropdown'), 'periodicForm.everyDay')
    await vi.advanceTimersByTimeAsync(400)
    expect(patches(testApp)).toEqual([])

    await vi.advanceTimersByTimeAsync(100)
    await flushPromises()
    expect(patches(testApp)).toEqual([
      [
        '/agent/10/triggers/1/',
        { service: { type: 'periodic', interval: 'DAY' } },
      ],
    ])
  })

  test('saves the last service value chosen within the debounce', async () => {
    useFakeTimers()
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(200, periodicTrigger())
    const wrapper = await mountSection([periodicTrigger()])
    const dropdown = wrapper.get('.agent-trigger-card .dropdown')

    await choose(dropdown, 'periodicForm.everyDay')
    await choose(dropdown, 'periodicForm.everyWeek')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(patches(testApp)).toEqual([
      [
        '/agent/10/triggers/1/',
        { service: { type: 'periodic', interval: 'WEEK' } },
      ],
    ])
  })

  test('shows why the service settings were rejected on the card', async () => {
    useFakeTimers()
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(400, {
      error: 'ERROR_TRIGGER_SERVICE_MISCONFIGURED',
      detail: 'The schedule is invalid.',
    })
    const wrapper = await mountSection([periodicTrigger()])
    const card = wrapper.get('.agent-trigger-card')
    expect(card.find('[role="alert"]').exists()).toBe(false)

    await choose(card.get('.dropdown'), 'periodicForm.everyDay')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(card.get('[role="alert"]').text()).toBe('The schedule is invalid.')
  })

  test('sends a rejected service value again with the next service edit', async () => {
    useFakeTimers()
    testApp.mock
      .onPatch('/agent/10/triggers/1/')
      .replyOnce(400, {
        error: 'ERROR_TRIGGER_SERVICE_MISCONFIGURED',
        detail: 'The schedule is invalid.',
      })
      .onPatch('/agent/10/triggers/1/')
      .reply((config) => {
        const saved = periodicTrigger()
        const body = JSON.parse(config.data)
        return [
          200,
          { ...saved, ...body, service: { ...saved.service, ...body.service } },
        ]
      })
    const wrapper = await mountSection([periodicTrigger()])
    const card = wrapper.get('.agent-trigger-card')

    await choose(card.get('.dropdown'), 'periodicForm.everyDay')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    await card.get('.agent-trigger-card__switch').trigger('click')
    await flushPromises()
    expect(card.get('[role="alert"]').text()).toBe('The schedule is invalid.')

    await card.get('input[type="number"]').setValue(9)
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(patches(testApp)).toEqual([
      [
        '/agent/10/triggers/1/',
        { service: { type: 'periodic', interval: 'DAY' } },
      ],
      ['/agent/10/triggers/1/', { enabled: false }],
      [
        '/agent/10/triggers/1/',
        { service: { type: 'periodic', interval: 'DAY', hour: '9' } },
      ],
    ])
    expect(card.find('[role="alert"]').exists()).toBe(false)
  })

  test('a message edited with rejected service values is saved alone', async () => {
    useFakeTimers()
    testApp.mock.onPatch('/agent/10/triggers/1/').reply((config) => {
      const body = JSON.parse(config.data)
      return body.service
        ? [
            400,
            {
              error: 'ERROR_TRIGGER_SERVICE_MISCONFIGURED',
              detail: 'The schedule is invalid.',
            },
          ]
        : [200, periodicTrigger(body)]
    })
    const wrapper = await mountSection([periodicTrigger()])
    const card = wrapper.get('.agent-trigger-card')
    const message = { formula: "'Changed'", mode: 'simple', version: '0.1' }
    const editMessage = (value) =>
      card
        .findComponent(AgentTriggerMessageInput)
        .vm.$emit('update:modelValue', value)

    await choose(card.get('.dropdown'), 'periodicForm.everyDay')
    editMessage(message)
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    const again = { ...message, formula: "'Again'" }
    editMessage(again)
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(patches(testApp).map(([, body]) => body)).toEqual([
      { message },
      { service: { type: 'periodic', interval: 'DAY' } },
      { message: again },
    ])
    expect(card.get('[role="alert"]').text()).toBe('The schedule is invalid.')
  })

  test('a save waits for the one in flight, whose older reply keeps the newer edit', async () => {
    useFakeTimers()
    let answerFirst
    testApp.mock
      .onPatch('/agent/10/triggers/1/')
      .replyOnce(
        () =>
          new Promise((resolve) => {
            answerFirst = resolve
          })
      )
      .onPatch('/agent/10/triggers/1/')
      .reply((config) => [
        200,
        periodicTrigger({
          service: {
            ...periodicTrigger().service,
            ...JSON.parse(config.data).service,
          },
        }),
      ])
    const wrapper = await mountSection([periodicTrigger()])
    const dropdown = wrapper.get('.agent-trigger-card .dropdown')

    await choose(dropdown, 'periodicForm.everyDay')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    await choose(dropdown, 'periodicForm.everyWeek')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    expect(patches(testApp)).toHaveLength(1)

    answerFirst([
      200,
      periodicTrigger({
        service: { ...periodicTrigger().service, interval: 'DAY' },
      }),
    ])
    await flushPromises()

    expect(patches(testApp).map(([, body]) => body.service.interval)).toEqual([
      'DAY',
      'WEEK',
    ])
    expect(dropdown.text()).toContain('periodicForm.everyWeek')
  })

  test('a switch flipped while a rejected service save is in flight is saved alone', async () => {
    useFakeTimers()
    const rejected = [
      400,
      {
        error: 'ERROR_TRIGGER_SERVICE_MISCONFIGURED',
        detail: 'The schedule is invalid.',
      },
    ]
    let answerFirst
    testApp.mock
      .onPatch('/agent/10/triggers/1/')
      .replyOnce(
        () =>
          new Promise((resolve) => {
            answerFirst = resolve
          })
      )
      .onPatch('/agent/10/triggers/1/')
      .reply((config) => {
        const body = JSON.parse(config.data)
        return body.service ? rejected : [200, periodicTrigger(body)]
      })
    const wrapper = await mountSection([periodicTrigger()])
    const card = wrapper.get('.agent-trigger-card')

    await choose(card.get('.dropdown'), 'periodicForm.everyDay')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    await card.get('.agent-trigger-card__switch').trigger('click')
    await flushPromises()
    answerFirst(rejected)
    await flushPromises()

    expect(patches(testApp).map(([, body]) => body)).toEqual([
      { service: { type: 'periodic', interval: 'DAY' } },
      { enabled: false },
    ])
    expect(
      card.get('.agent-trigger-card__switch').attributes('aria-checked')
    ).toBe('false')
    expect(card.get('[role="alert"]').text()).toBe('The schedule is invalid.')
  })

  test('a failed save shows the saved value again without reloading the list', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(500)
    const wrapper = await mountSection([periodicTrigger()])
    const toggle = () => wrapper.get('.agent-trigger-card__switch')

    await toggle().trigger('click')
    await flushPromises()

    expect(toggle().attributes('aria-checked')).toBe('true')
    expect(
      testApp.mock.history.get.filter(
        ({ url }) => url === '/agent/10/triggers/'
      )
    ).toHaveLength(1)
  })

  test('a failed service save shows the saved schedule in the form again', async () => {
    useFakeTimers()
    testApp.dontFailOnErrorResponses()
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(500)
    const wrapper = await mountSection([periodicTrigger()])
    const dropdown = () => wrapper.get('.agent-trigger-card .dropdown')

    await choose(dropdown(), 'periodicForm.everyDay')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(dropdown().get('.dropdown__selected-text').text()).toBe(
      'periodicForm.everyHour'
    )
  })

  test('a trigger deleted elsewhere stays removed after its delete fails', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onDelete('/agent/10/triggers/1/').reply(404, {
      error: 'ERROR_AGENT_TRIGGER_DOES_NOT_EXIST',
    })
    const wrapper = await mountSection([periodicTrigger()])

    await wrapper.get('.agent-trigger-card__delete').trigger('click')
    await flushPromises()

    expect(wrapper.find('.agent-trigger-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('agent.noTriggers')
  })

  test('a read-only member edits nothing', async () => {
    useFakeTimers()
    const wrapper = await mountSection([periodicTrigger()], ['periodic'], false)

    await choose(
      wrapper.get('.agent-trigger-card .dropdown'),
      'periodicForm.everyDay'
    )
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(patches(testApp)).toEqual([])
    expect(wrapper.find('.agent-trigger-card__delete').exists()).toBe(false)
  })

  test('a trigger of an unknown type shows its type and can be deleted', async () => {
    testApp.mock.onDelete('/agent/10/triggers/1/').reply(204)
    const wrapper = await mountSection([
      periodicTrigger({ type: 'removed_plugin_trigger' }),
    ])

    expect(wrapper.get('.agent-trigger-card__name').text()).toBe(
      'removed_plugin_trigger'
    )
    await wrapper.get('.agent-trigger-card__delete').trigger('click')
    await flushPromises()
    expect(wrapper.find('.agent-trigger-card').exists()).toBe(false)
  })

  test('switches a trigger off at once and deletes it', async () => {
    testApp.mock
      .onPatch('/agent/10/triggers/1/')
      .reply(200, periodicTrigger({ enabled: false }))
    testApp.mock.onDelete('/agent/10/triggers/1/').reply(204)
    const wrapper = await mountSection([periodicTrigger()])

    await wrapper.get('.agent-trigger-card__switch').trigger('click')
    await flushPromises()
    expect(patches(testApp)).toEqual([
      ['/agent/10/triggers/1/', { enabled: false }],
    ])
    expect(
      wrapper.get('.agent-trigger-card__switch').attributes('aria-checked')
    ).toBe('false')

    await wrapper.get('.agent-trigger-card__delete').trigger('click')
    await flushPromises()
    expect(testApp.mock.history.delete.map(({ url }) => url)).toEqual([
      '/agent/10/triggers/1/',
    ])
    expect(wrapper.find('.agent-trigger-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('agent.noTriggers')
  })

  test('offers to add a trigger only once the list has loaded', async () => {
    const list = deferredReply()
    testApp.mock.onGet('/agent/10/triggers/').replyOnce(list.reply)
    const wrapper = await mountSection([])
    expect(wrapper.find('.agent-triggers__add').exists()).toBe(false)

    list.resolve(500, {})
    await flushPromises()
    expect(wrapper.text()).toContain('agent.triggersLoadError')
    expect(wrapper.find('.agent-triggers__add').exists()).toBe(false)

    await wrapper.get('.alert button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('agent.noTriggers')
    expect(wrapper.find('.agent-triggers__add').exists()).toBe(true)
  })

  test('offers only the available trigger types that are enabled and creates the picked one', async () => {
    const service = periodicTrigger().service
    const defaults = {
      interval: 'DAY',
      hour: 9,
      minute: 0,
      timezone: moment.tz.guess(),
    }
    const created = periodicTrigger({
      id: 2,
      service: { ...service, ...defaults, id: 6 },
    })
    testApp.mock.onPost('/agent/10/triggers/').reply(200, created)
    const wrapper = await mountSection([], ['periodic', 'http_trigger'])
    expect(wrapper.text()).toContain('agent.noTriggers')

    await wrapper.get('.agent-triggers__add').trigger('click')
    await flushPromises()
    const items = wrapper
      .findComponent(AgentTriggerPicker)
      .findAll('.grouped-menu__actions .menu-list__item-button')
    expect(
      items.map((item) => item.get('.menu-list__item-label').text())
    ).toEqual(['serviceType.corePeriodic'])

    await items[0].trigger('click')
    await flushPromises()
    expect(
      testApp.mock.history.post.map(({ url, data }) => [url, JSON.parse(data)])
    ).toEqual([
      [
        '/agent/10/triggers/',
        {
          type: 'periodic',
          message: {
            formula:
              "concat('agent.triggerDefaultMessage ', get('trigger.fired_at'))",
            mode: 'simple',
            version: '0.1',
          },
          service: defaults,
        },
      ],
    ])
    const card = wrapper.get('.agent-trigger-card')
    expect(card.find('.agent-trigger-card__status').exists()).toBe(false)
  })

  test('opens a new trigger with the translated name and the time it fired', async () => {
    const { createI18n } = await vi.importActual('vue-i18n')
    const { t } = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en: { ...agentLocale, ...integrationsLocale } },
    }).global

    const periodic = new CorePeriodicTriggerServiceType({
      app: { $i18n: { t } },
    })

    expect(defaultTriggerMessage(t, periodic)).toEqual({
      formula: "concat('Periodic trigger fired at ', get('trigger.fired_at'))",
      mode: 'simple',
      version: '0.1',
    })
  })

  test('shows the default message as text followed by a Fired at chip', async () => {
    const trigger = periodicTrigger({
      message: defaultTriggerMessage(
        (key, values) => `${values.trigger} fired at`,
        { name: 'Periodic trigger', getEventDescriptionTemplate: () => null }
      ),
    })
    const wrapper = await testApp.mount(AgentTriggerMessageInput, {
      props: { modelValue: trigger.message },
      global: {
        provide: { applicationContext: reactive({ agent, trigger }) },
      },
    })
    await flushPromises()
    const chips = wrapper.findAll('.get-formula-component')

    expect(wrapper.text()).toContain('Periodic trigger fired at')
    expect(chips.map((chip) => chip.text())).toEqual([
      'agent.triggerData agent.triggerFiredAt',
    ])
  })

  test('marks an incomplete trigger on its header until it is configured', async () => {
    const service = { ...periodicTrigger().service, interval: null }
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(200, periodicTrigger())
    const wrapper = await mountSection([periodicTrigger({ service })])
    const card = wrapper.get('.agent-trigger-card')

    expect(card.text()).not.toContain(
      'serviceType.corePeriodicErrorIntervalMissing'
    )
    expect(
      card.get('.agent-trigger-card__status').attributes('aria-label')
    ).toBe('serviceType.corePeriodicErrorIntervalMissing')

    await choose(card.get('.dropdown'), 'periodicForm.everyHour')

    expect(card.find('.agent-trigger-card__status').exists()).toBe(false)
  })

  test('counts the data the trigger provides and lists it once expanded', async () => {
    const wrapper = await mountSection([periodicTrigger()])
    const toggle = wrapper.get('.agent-trigger-card__schema-toggle')

    expect(toggle.get('.agent-trigger-card__schema-title').text()).toBe(
      'agent.triggerDataProvides'
    )
    expect(toggle.get('.agent-trigger-card__schema-count').text()).toBe(
      'agent.triggerDataValues - 3'
    )
    expect(toggle.attributes('aria-expanded')).toBe('false')

    await toggle.trigger('click')

    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(
      wrapper.findAll('.agent-trigger-card__schema-list li').map((item) => {
        return item.text()
      })
    ).toEqual([
      'Previous scheduled runstring',
      'Next scheduled runstring',
      'agent.triggerFiredAtstring',
    ])
  })

  test('edits the formula of the opening message object and keeps its mode', async () => {
    const trigger = periodicTrigger({
      message: { formula: "'Check'", mode: 'advanced', version: '0.1' },
    })
    const wrapper = await testApp.mount(AgentTriggerMessageInput, {
      props: { modelValue: trigger.message },
      global: {
        provide: { applicationContext: reactive({ agent, trigger }) },
      },
    })
    const field = wrapper.findComponent(FormulaInputField)
    expect([field.props('value'), field.props('mode')]).toEqual([
      "'Check'",
      'advanced',
    ])

    field.vm.$emit('input', "'Daily check'")
    expect(wrapper.emitted('update:modelValue')).toEqual([
      [{ formula: "'Daily check'", mode: 'advanced', version: '0.1' }],
    ])
  })

  test('offers the trigger payload as formula variables in the opening message', async () => {
    const trigger = periodicTrigger()
    const wrapper = await testApp.mount(AgentTriggerMessageInput, {
      props: { modelValue: trigger.message },
      global: {
        provide: { applicationContext: reactive({ agent, trigger }) },
      },
    })
    const [dataGroup] = wrapper
      .findComponent(FormulaInputField)
      .props('nodesHierarchy')

    expect(dataGroup.type).toBe('data')
    expect(dataGroup.nodes.map((node) => node.identifier)).toEqual(['trigger'])
    expect(dataGroup.nodes[0].name).toBe('agent.triggerData')
    expect(dataGroup.nodes[0].nodes.map((node) => node.name)).toEqual([
      'Previous scheduled run',
      'Next scheduled run',
      'agent.triggerFiredAt',
    ])
  })

  test('cuts a long name by characters, never inside an emoji', async () => {
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(200, periodicTrigger())
    const wrapper = await mountSection([periodicTrigger()])
    const name = wrapper.get('.agent-trigger-card__name-text')
    const kept = `${'x'.repeat(74)}😀`

    await wrapper.get('.agent-trigger-card__rename').trigger('click')
    name.element.textContent = `${kept}😀`
    await name.trigger('input')
    await name.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(patches(testApp)).toEqual([
      ['/agent/10/triggers/1/', { name: kept }],
    ])
  })

  test('offers the overlap rule as radios in its own section and saves a choice at once', async () => {
    testApp.mock
      .onPatch('/agent/10/triggers/1/')
      .reply(200, periodicTrigger({ on_overlap: 'wait' }))
    const wrapper = await mountSection([periodicTrigger()])
    const section = wrapper.get('.agent-trigger-card__overlap')
    const group = section.get('[role="radiogroup"]')
    const radios = group.findAll('input[type="radio"]')
    const checked = () => radios.map((radio) => radio.element.checked)

    expect(
      section.get(`[id="${group.attributes('aria-labelledby')}"]`).text()
    ).toBe('agent.triggerOnOverlap')
    expect(
      section.get(`[id="${group.attributes('aria-describedby')}"]`).text()
    ).toBe('agent.triggerOnOverlapDescription')
    expect(
      radios.map((radio) =>
        wrapper
          .get(`[id="${radio.attributes('aria-labelledby')}"]`)
          .findAll(
            '.agent-trigger-card__overlap-option-label, .agent-trigger-card__overlap-option-hint'
          )
          .map((part) => part.text())
      )
    ).toEqual([
      [
        'agent.triggerOnOverlapSkip agent.triggerOnOverlapRecommended',
        'agent.triggerOnOverlapSkipHint - 10',
      ],
      ['agent.triggerOnOverlapWait', 'agent.triggerOnOverlapWaitHint - 10'],
      [
        'agent.triggerOnOverlapParallel',
        'agent.triggerOnOverlapParallelHint - 5',
      ],
    ])
    expect(new Set(radios.map((radio) => radio.attributes('name'))).size).toBe(
      1
    )
    expect(checked()).toEqual([true, false, false])

    await radios[1].trigger('click')
    await flushPromises()

    expect(patches(testApp)).toEqual([
      ['/agent/10/triggers/1/', { on_overlap: 'wait' }],
    ])
    expect(checked()).toEqual([false, true, false])
  })

  test('tells how many runs can wait, as the server allows', async () => {
    const wrapper = await mountSection(
      [periodicTrigger()],
      ['periodic'],
      true,
      3
    )
    const hints = wrapper.findAll('.agent-trigger-card__overlap-option-hint')

    expect(hints[1].text()).toBe('agent.triggerOnOverlapWaitHint - 3')
  })

  test('tells runs can wait indefinitely when the server has no cap', async () => {
    const wrapper = await mountSection(
      [periodicTrigger()],
      ['periodic'],
      true,
      0
    )
    const hints = wrapper.findAll('.agent-trigger-card__overlap-option-hint')

    expect(hints[1].text()).toBe('agent.triggerOnOverlapWaitUnlimitedHint')
  })

  test.each([
    [10, 5, 'agent.triggerOnOverlapParallelHint - 5'],
    [0, 5, 'agent.triggerOnOverlapParallelQueueUnlimitedHint - 5'],
    [10, 0, 'agent.triggerOnOverlapParallelUnlimitedHint'],
  ])(
    'words the parallel hint by both caps: %s queued, %s at once',
    async (maxQueued, maxParallel, hint) => {
      const wrapper = await mountSection(
        [periodicTrigger()],
        ['periodic'],
        true,
        maxQueued,
        { max_parallel_trigger_runs: maxParallel }
      )
      const hints = wrapper.findAll('.agent-trigger-card__overlap-option-hint')

      expect(hints[2].text()).toBe(hint)
    }
  )

  test.each([
    ['rate_limited', 'agent.triggerSkippedRateLimited'],
    ['agent_rate_limited', 'agent.triggerSkippedAgentRateLimited'],
    ['previous_running', 'agent.triggerSkippedPreviousRunning'],
    ['queue_full', 'agent.triggerSkippedQueueFull'],
    ['no_access', 'agent.triggerSkippedNoAccess'],
    ['event_too_large', 'agent.triggerSkippedEventTooLarge'],
  ])(
    'says why a firing was skipped until a later one is accepted: %s',
    async (reason, text) => {
      const skipped = {
        last_skipped_on: '2026-11-10T10:42:00Z',
        last_skipped_reason: reason,
      }
      const wrapper = await mountSection([
        periodicTrigger(skipped),
        periodicTrigger({
          ...skipped,
          id: 2,
          last_fired_on: '2026-11-10T10:43:00Z',
        }),
      ])
      const [shown, hidden] = wrapper.findAll('.agent-trigger-card')

      expect(
        shown
          .get(
            '.agent-trigger-card__overlap [role="radiogroup"] + .agent-trigger-card__skipped'
          )
          .text()
      ).toBe(text)
      expect(hidden.find('.agent-trigger-card__skipped').exists()).toBe(false)
    }
  )

  test('keeps the skip line when the last accepted firing was before it', async () => {
    const wrapper = await mountSection([
      periodicTrigger({
        last_fired_on: '2026-11-10T10:41:00Z',
        last_skipped_on: '2026-11-10T10:42:00Z',
        last_skipped_reason: 'rate_limited',
      }),
    ])

    expect(wrapper.get('.agent-trigger-card__skipped').text()).toBe(
      'agent.triggerSkippedRateLimited'
    )
  })

  test('offers the tables the run identity reads and shows the saved one', async () => {
    const wrapper = await mountSection(
      [rowsTrigger()],
      ['local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )
    const card = wrapper.get('.agent-trigger-card')

    expect(
      card.findAll('.dropdown__selected-text').map((item) => item.text())
    ).toEqual(['Sales', 'Orders'])
    expect(card.find('.agent-trigger-card__note').exists()).toBe(false)
    expect(patches(testApp)).toEqual([])
  })

  test('asks for workspace access, and reloads the choices once the agent has it', async () => {
    testApp.mock.onGet('/agent/10/trigger-types/').replyOnce(200, [
      triggerTypeOf('periodic'),
      {
        type: 'local_baserow_rows_created',
        form_choices: { databases: [] },
        default_on_overlap: 'wait',
      },
    ])
    const types = ['periodic', 'local_baserow_rows_created']
    const wrapper = await mountSection(
      [periodicTrigger(), rowsTrigger()],
      types
    )
    const rowsCard = () => wrapper.findAll('.agent-trigger-card')[1]
    const notes = () =>
      wrapper.findAll('.agent-trigger-card__note').map((note) => note.text())
    const selected = () =>
      rowsCard()
        .findAll('.dropdown__selected-text')
        .map((item) => item.text())

    expect(notes()).toEqual(['agent.triggerNeedsWorkspaceAccess'])
    expect(rowsCard().find('.agent-trigger-card__note').exists()).toBe(true)
    expect(selected()).not.toContain('Orders')

    await wrapper.setProps({
      configuration: completeConfiguration({
        available_trigger_types: types,
        max_queued_trigger_runs: 10,
        ...activeRunAs,
      }),
    })
    await flushPromises()

    expect(notes()).toEqual([])
    expect(selected()).toEqual(['Sales', 'Orders'])
  })

  test('retries the trigger types with the list when both failed to load', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/agent/10/triggers/').replyOnce(500)
    testApp.mock.onGet('/agent/10/trigger-types/').replyOnce(500)
    const wrapper = await mountSection(
      [rowsTrigger()],
      ['local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )

    await wrapper.get('.alert__actions button').trigger('click')
    await flushPromises()

    expect(
      wrapper.findAll('.dropdown__selected-text').map((item) => item.text())
    ).toEqual(['Sales', 'Orders'])
  })

  test('offers to retry the trigger types alone when only they failed to load', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/agent/10/trigger-types/').replyOnce(500)
    const wrapper = await mountSection(
      [rowsTrigger()],
      ['local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )
    expect(wrapper.text()).toContain('agent.triggerTypesLoadError')

    await wrapper.get('.alert__actions button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('agent.triggerTypesLoadError')
    expect(testApp.mock.history.get.map(({ url }) => url)).toEqual([
      '/agent/10/triggers/',
      '/agent/10/trigger-types/',
      '/agent/10/trigger-types/',
    ])
    expect(
      wrapper.findAll('.dropdown__selected-text').map((item) => item.text())
    ).toEqual(['Sales', 'Orders'])
  })

  test('saves how many rows each conversation gets, for list triggers only', async () => {
    useFakeTimers()
    testApp.mock
      .onPatch('/agent/10/triggers/2/')
      .reply(200, rowsTrigger({ batch_size: 5 }))
    const wrapper = await mountSection(
      [periodicTrigger(), rowsTrigger()],
      ['periodic', 'local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )
    const [periodicCard, rowsCard] = wrapper.findAll('.agent-trigger-card')
    const field = rowsCard.get('.agent-trigger-card__batch-size')

    expect(periodicCard.find('.agent-trigger-card__batch-size').exists()).toBe(
      false
    )
    expect(field.text()).toContain('agent.triggerBatchSizeHelper')

    await field.get('input').setValue(0)
    await field.get('input').setValue(5)
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(patches(testApp)).toEqual([
      ['/agent/10/triggers/2/', { batch_size: 5 }],
    ])
  })

  test('rejects a batch size outside 1 to 100 without saving what was typed on the way', async () => {
    useFakeTimers()
    const wrapper = await mountSection(
      [rowsTrigger()],
      ['local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )
    const field = wrapper.get('.agent-trigger-card__batch-size')
    const input = field.get('input')

    for (const typed of [1, 15, 150]) await input.setValue(typed)
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(field.text()).toContain('agent.triggerBatchSizeInvalid')
    expect(patches(testApp)).toEqual([])

    await input.trigger('blur')

    expect(input.element.value).toBe('20')
    expect(field.text()).not.toContain('agent.triggerBatchSizeInvalid')
  })

  test('lists the rows, their count and table, and when it fired', async () => {
    const wrapper = await mountSection(
      [rowsTrigger()],
      ['local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )

    await wrapper.get('.agent-trigger-card__schema-toggle').trigger('click')

    expect(
      wrapper
        .findAll('.agent-trigger-card__schema-list li')
        .map((item) => item.text())
    ).toEqual([
      'agent.triggerRowsarray',
      'serviceType.eventCountnumber',
      'serviceType.eventTablestring',
      'agent.triggerFiredAtstring',
    ])
  })

  test('recommends the overlap rule the trigger type defaults to', async () => {
    const wrapper = await mountSection(
      [rowsTrigger()],
      ['local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )

    expect(
      wrapper
        .findAll('.agent-trigger-card__overlap-option-label')
        .map((label) => label.text())
    ).toEqual([
      'agent.triggerOnOverlapSkip',
      'agent.triggerOnOverlapWait agent.triggerOnOverlapRecommended',
      'agent.triggerOnOverlapParallel',
    ])
  })

  test('opens a new row trigger with how many rows changed where, and the rows', async () => {
    const { createI18n } = await vi.importActual('vue-i18n')
    const { t } = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en: { ...agentLocale, ...integrationsLocale } },
    }).global
    const rowsCreated = new LocalBaserowRowsCreatedTriggerServiceType({
      app: { $i18n: { t } },
    })

    expect(defaultTriggerMessage(t, rowsCreated)).toEqual(DEFAULT_ROWS_MESSAGE)
  })

  test('shows the default row message as Count, Table and Rows chips', async () => {
    const trigger = rowsTrigger({ message: DEFAULT_ROWS_MESSAGE })
    const wrapper = await testApp.mount(AgentTriggerMessageInput, {
      props: { modelValue: trigger.message },
      global: {
        provide: { applicationContext: reactive({ agent, trigger }) },
      },
    })
    await flushPromises()

    expect(
      wrapper.findAll('.get-formula-component').map((chip) => chip.text())
    ).toEqual([
      'agent.triggerData serviceType.eventCount',
      'agent.triggerData serviceType.eventTable',
      'agent.triggerData agent.triggerRows',
    ])
    expect(wrapper.text()).toContain('rows were created in')
    expect(
      wrapper.findComponent(FormulaInputField).props('allowNodeSelection')
    ).toBe('array')
  })

  test('shows when the run identity cannot read the table and turns the switch back off until a switch-on is accepted', async () => {
    testApp.mock.onPatch('/agent/10/triggers/2/').replyOnce(400, {
      error: 'ERROR_AGENT_TRIGGER_NO_ACCESS',
      detail:
        "The agent's workspace access can't read what this trigger watches.",
    })
    testApp.mock.onPatch('/agent/10/triggers/2/').reply(200, rowsTrigger())
    const wrapper = await mountSection(
      [rowsTrigger({ enabled: false })],
      ['local_baserow_rows_created'],
      true,
      10,
      activeRunAs
    )
    const card = wrapper.get('.agent-trigger-card')

    await card.get('.agent-trigger-card__switch').trigger('click')
    await flushPromises()

    expect(patches(testApp)).toEqual([
      ['/agent/10/triggers/2/', { enabled: true }],
    ])
    expect(card.get('[role="alert"]').text()).toBe('agent.triggerNoAccess')
    expect(
      card.get('.agent-trigger-card__switch').attributes('aria-checked')
    ).toBe('false')

    await card.get('.agent-trigger-card__switch').trigger('click')
    await flushPromises()

    expect(card.find('[role="alert"]').exists()).toBe(false)
    expect(
      card.get('.agent-trigger-card__switch').attributes('aria-checked')
    ).toBe('true')
  })

  test('shows a trigger by its name, else by the default its type words', async () => {
    const wrapper = await mountSection(
      [
        periodicTrigger(),
        periodicTrigger({ id: 3, name: 'Morning digest' }),
        rowsTrigger(),
        rowsTrigger({
          id: 4,
          service: { ...rowsTrigger().service, table_id: 99 },
        }),
      ],
      ['periodic', 'local_baserow_rows_created']
    )

    expect(
      wrapper.findAll('.agent-trigger-card__name').map((name) => name.text())
    ).toEqual([
      'serviceType.corePeriodicNameHour',
      'Morning digest',
      'serviceType.localBaserowRowsCreatedInTable',
      'serviceType.localBaserowRowsCreated',
    ])
  })

  test('renames a trigger inline, and clearing the name shows the default again', async () => {
    testApp.mock
      .onPatch('/agent/10/triggers/1/')
      .replyOnce(200, periodicTrigger({ name: 'Morning digest' }))
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(200, periodicTrigger())
    const wrapper = await mountSection([periodicTrigger()])
    const name = wrapper.get('.agent-trigger-card__name-text')
    const rename = async (text, endKey) => {
      await wrapper.get('.agent-trigger-card__rename').trigger('click')
      name.element.textContent = text
      await name.trigger('input')
      await (endKey
        ? name.trigger('keydown', { key: endKey })
        : name.trigger('focusout'))
      await flushPromises()
    }

    await rename('  Morning digest ', 'Enter')

    expect(name.text()).toBe('Morning digest')

    await rename('', null)

    expect(patches(testApp)).toEqual([
      ['/agent/10/triggers/1/', { name: 'Morning digest' }],
      ['/agent/10/triggers/1/', { name: '' }],
    ])
    expect(name.text()).toBe('serviceType.corePeriodicNameHour')
  })

  test.each([
    ['swaps the default message for the new type default', true],
    ['keeps a message of its own', false],
  ])(
    'changes the trigger type from its header and %s',
    async (_, defaultMessage) => {
      const defaultOf = (type) =>
        defaultTriggerMessage(
          (key) => key,
          testApp.getRegistry().get('service', type)
        )
      const message = defaultMessage
        ? defaultOf('periodic')
        : periodicTrigger().message
      const changed = rowsTrigger({ id: 1, message: DEFAULT_ROWS_MESSAGE })
      testApp.mock.onPatch('/agent/10/triggers/1/').reply(200, changed)
      const wrapper = await mountSection(
        [periodicTrigger({ message })],
        ['periodic', 'local_baserow_rows_created']
      )
      const card = wrapper.get('.agent-trigger-card')

      await card.get('.agent-trigger-card__type').trigger('click')
      await flushPromises()
      const picker = card.findComponent(AgentTriggerPicker)
      await picker
        .get('.menu-search__input')
        .setValue('serviceType.localBaserowRowsCreated')
      await picker
        .get('.grouped-menu__actions .menu-list__item-button')
        .trigger('click')
      await flushPromises()

      expect(patches(testApp)).toEqual([
        [
          '/agent/10/triggers/1/',
          {
            type: 'local_baserow_rows_created',
            service: { type: 'local_baserow_rows_created' },
            ...(defaultMessage
              ? { message: defaultOf('local_baserow_rows_created') }
              : {}),
          },
        ],
      ])
      expect(
        card
          .findComponent({ name: 'LocalBaserowSignalTriggerServiceForm' })
          .exists()
      ).toBe(true)
      expect(card.find('.agent-trigger-card__batch-size').exists()).toBe(true)
      expect(
        card
          .findAll('.agent-trigger-card__overlap-option-label')
          .map((label) => label.text())
      ).toEqual([
        'agent.triggerOnOverlapSkip',
        'agent.triggerOnOverlapWait agent.triggerOnOverlapRecommended',
        'agent.triggerOnOverlapParallel',
      ])
      expect(card.get('.agent-trigger-card__schema-count').text()).toBe(
        'agent.triggerDataValues - 4'
      )
    }
  )
})
