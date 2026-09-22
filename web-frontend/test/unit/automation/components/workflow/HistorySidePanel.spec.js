import { ref } from 'vue'
import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import HistorySidePanel from '@baserow/modules/automation/components/workflow/sidePanels/HistorySidePanel.vue'
import { registerRealtimeEvents } from '@baserow/modules/automation/realtime'

describe('HistorySidePanel pagination', () => {
  let testApp
  let workflow
  let events

  const histories = Array.from({ length: 45 }, (_, index) => ({
    id: 45 - index,
    status: 'success',
    started_on: '2026-09-22T10:00:00Z',
    completed_on: '2026-09-22T10:00:02Z',
    message: `Execution ${45 - index}`,
    is_test_run: false,
    triggered_by: null,
  }))

  beforeEach(() => {
    testApp = new TestApp()
    workflow = ref({ id: 7, _: {} })
    testApp.store.commit('automationWorkflow/SET_SELECTED', {
      automation: { workflows: [workflow.value] },
      workflow: workflow.value,
    })
    events = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => {
        events[name] = handler
      },
    })
    testApp.mock.onGet('automation/workflows/7/history/').reply((config) => {
      const { page = 1, size = 100 } = config.params || {}
      return [
        200,
        {
          count: 45,
          success_count: 40,
          fail_count: 5,
          results: histories.slice((page - 1) * size, page * size),
        },
      ]
    })
    testApp.mock
      .onGet(/automation\/workflow_histories\/\d+\/node_histories\//)
      .reply(200, [])
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountPanel = () =>
    testApp.mount(HistorySidePanel, {
      global: { provide: { workflow } },
    })

  test('paginates by 20 with global counters and resets expanded runs on navigation', async () => {
    const wrapper = await mountPanel()
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(20)
    expect(
      wrapper
        .findAll('.history-side-panel__counts-runs-total')
        .map((el) => el.text())
    ).toEqual(['40', '5'])
    await wrapper.get('.expandable__header').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Execution 45')
    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.get('.paginator input').element.value).toBe('2')
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(20)
    expect(wrapper.find('.expandable--expanded').exists()).toBe(false)
    await wrapper.get('.expandable__header').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Execution 25')
    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(5)
    expect(wrapper.get('.paginator input').element.value).toBe('3')
  })

  test('keeps older pages stable when a run starts or finishes and refresh returns to page one', async () => {
    const wrapper = await mountPanel()
    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    await wrapper.get('.expandable__header').trigger('click')
    await flushPromises()
    for (const name of [
      'automation_workflow_dispatch_started',
      'automation_workflow_dispatch_cancellation_requested',
      'automation_workflow_dispatch_done',
    ]) {
      events[name]({ store: testApp.store }, { workflow_id: 7 })
      await flushPromises()
      expect(wrapper.text()).toContain('Execution 25')
      expect(wrapper.get('.paginator input').element.value).toBe('2')
    }
    await wrapper.get('.iconoir-refresh').trigger('click')
    await flushPromises()
    expect(wrapper.get('.paginator input').element.value).toBe('1')
    await wrapper.get('.expandable__header').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Execution 45')
  })

  test('ignores a late realtime response after navigating to an older page', async () => {
    const wrapper = await mountPanel()
    let finishRefresh
    testApp.mock.onGet('automation/workflows/7/history/').reply((config) => {
      if (config.params.page === 1) {
        return new Promise((resolve) => {
          finishRefresh = resolve
        })
      }
      return [
        200,
        {
          count: 45,
          success_count: 40,
          fail_count: 5,
          results: histories.slice(20, 40),
        },
      ]
    })
    events.automation_workflow_dispatch_started(
      { store: testApp.store },
      { workflow_id: 7 }
    )
    await flushPromises()
    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    finishRefresh([200, { count: 45, results: histories.slice(0, 20) }])
    await flushPromises()
    await wrapper.get('.expandable__header').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Execution 25')
    expect(wrapper.get('.paginator input').element.value).toBe('2')
  })

  test('updates page one without closing a run that remains visible', async () => {
    const wrapper = await mountPanel()
    await wrapper.get('.expandable__header').trigger('click')
    await flushPromises()
    testApp.mock.onGet('automation/workflows/7/history/').reply(200, {
      count: 46,
      success_count: 41,
      fail_count: 5,
      results: [
        { ...histories[0], id: 46, message: 'New execution' },
        ...histories.slice(0, 19),
      ],
    })
    events.automation_workflow_dispatch_done(
      { store: testApp.store },
      { workflow_id: 7 }
    )
    await flushPromises()
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(20)
    expect(wrapper.findAll('.expandable--expanded')).toHaveLength(1)
    expect(wrapper.get('.expandable--expanded').text()).toContain(
      'Execution 45'
    )
    expect(
      wrapper.findAll('.history-side-panel__counts-runs-total')[0].text()
    ).toBe('41')
  })

  test('reopens on page one and resets when switching workflows', async () => {
    let wrapper = await mountPanel()
    await wrapper.get('.paginator input').setValue('3')
    await flushPromises()
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(5)
    wrapper.unmount()
    wrapper = await mountPanel()
    expect(wrapper.get('.paginator input').element.value).toBe('1')
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(20)
    testApp.mock.onGet('automation/workflows/8/history/').reply(200, {
      count: 0,
      success_count: 0,
      fail_count: 0,
      results: [],
    })
    workflow.value = { id: 8 }
    await flushPromises()
    expect(wrapper.find('.workflow-history__header').exists()).toBe(false)
    expect(wrapper.text()).toContain('historySidePanel.noRunsTitle')
    expect(wrapper.find('.paginator').exists()).toBe(false)
    expect(wrapper.find('.iconoir-refresh').exists()).toBe(true)
    expect(wrapper.find('.iconoir-cancel').exists()).toBe(true)
  })

  test('keeps the current page when loading another page fails and allows retry', async () => {
    const wrapper = await mountPanel()
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('automation/workflows/7/history/').reply(500)
    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.get('.paginator input').element.value).toBe('1')
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(20)
    testApp.mock.onGet('automation/workflows/7/history/').reply(200, {
      count: 45,
      success_count: 40,
      fail_count: 5,
      results: histories.slice(20, 40),
    })
    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.get('.paginator input').element.value).toBe('2')
  })

  test('uses the last available page if older history was pruned', async () => {
    const wrapper = await mountPanel()
    testApp.mock.onGet('automation/workflows/7/history/').reply((config) => [
      200,
      {
        count: 25,
        success_count: 20,
        fail_count: 5,
        results: config.params.page === 2 ? histories.slice(20, 25) : [],
      },
    ])
    await wrapper.get('.paginator input').setValue('3')
    await flushPromises()
    expect(wrapper.get('.paginator input').element.value).toBe('2')
    expect(wrapper.findAll('.workflow-history__header')).toHaveLength(5)
  })

  test('refreshes when a run finishes while the first page is still loading', async () => {
    let finishInitialLoad
    testApp.mock.onGet('automation/workflows/7/history/').reply(
      () =>
        new Promise((resolve) => {
          finishInitialLoad = resolve
        })
    )
    const wrapper = await mountPanel()
    events.automation_workflow_dispatch_done(
      { store: testApp.store },
      { workflow_id: 7 }
    )
    testApp.mock.onGet('automation/workflows/7/history/').reply(200, {
      count: 1,
      success_count: 1,
      fail_count: 0,
      results: [histories[0]],
    })
    finishInitialLoad([
      200,
      {
        count: 1,
        success_count: 0,
        fail_count: 0,
        results: [{ ...histories[0], status: 'started', completed_on: null }],
      },
    ])
    await flushPromises()
    expect(wrapper.get('.workflow-history__header-title').text()).toBe(
      'historySidePanel.statusSuccess'
    )
    expect(
      wrapper.findAll('.history-side-panel__counts-runs-total')[0].text()
    ).toBe('1')
  })

  test('coalesces realtime bursts while continuing to display completed responses', async () => {
    const wrapper = await mountPanel()
    const requests = []
    testApp.mock
      .onGet('automation/workflows/7/history/')
      .reply(() => new Promise((resolve) => requests.push(resolve)))
    const completeRun = () =>
      events.automation_workflow_dispatch_done(
        { store: testApp.store },
        { workflow_id: 7 }
      )
    completeRun()
    await flushPromises()
    for (let index = 0; index < 3; index++) {
      for (let event = 0; event < 5; event++) completeRun()
      await flushPromises()
      expect(requests).toHaveLength(index + 1)
      requests[index]([
        200,
        {
          count: 45,
          success_count: 41 + index,
          fail_count: 4 - index,
          results: histories.slice(0, 20),
        },
      ])
      await flushPromises()
      expect(
        wrapper.findAll('.history-side-panel__counts-runs-total')[0].text()
      ).toBe(String(41 + index))
      expect(requests).toHaveLength(index + 2)
      expect(wrapper.find('.loading').exists()).toBe(false)
    }
    requests[3]([
      200,
      {
        count: 45,
        success_count: 44,
        fail_count: 1,
        results: histories.slice(0, 20),
      },
    ])
    await flushPromises()
    expect(requests).toHaveLength(4)
    expect(
      wrapper.findAll('.history-side-panel__counts-runs-total')[0].text()
    ).toBe('44')
  })

  test('does not reset the current page scroll when an initial deferred refresh finishes', async () => {
    const requests = []
    testApp.mock
      .onGet('automation/workflows/7/history/')
      .reply(() => new Promise((resolve) => requests.push(resolve)))
    const wrapper = await mountPanel()
    events.automation_workflow_dispatch_done(
      { store: testApp.store },
      { workflow_id: 7 }
    )
    requests[0]([200, { count: 45, results: histories.slice(0, 20) }])
    await flushPromises()
    expect(requests).toHaveLength(2)
    await wrapper.findAll('.paginator__button')[1].trigger('click')
    await flushPromises()
    requests[2]([200, { count: 45, results: histories.slice(20, 40) }])
    await flushPromises()
    const content = wrapper.get('.history-side-panel__content').element
    content.scrollTop = 300
    requests[1]([200, { count: 45, results: histories.slice(0, 20) }])
    await flushPromises()
    expect(wrapper.get('.paginator input').element.value).toBe('2')
    expect(content.scrollTop).toBe(300)
  })
})
