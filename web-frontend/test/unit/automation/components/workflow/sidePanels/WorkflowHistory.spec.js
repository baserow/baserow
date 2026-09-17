import { ref } from 'vue'
import { createStore } from 'vuex'
import { mount, flushPromises } from '@vue/test-utils'
import WorkflowHistory from '@baserow/modules/automation/components/workflow/sidePanels/WorkflowHistory'

// Mounted on a fresh Vue app rather than through TestApp/mountSuspended on
// purpose: the component reads `useNuxtApp().$hasPermission`, which Nuxt defines
// on the real test app as a non-configurable getter, so it can't be spied or
// overridden per test. `useNuxtApp()` resolves the mounting Vue app's `$nuxt`
// first, so a tiny plugin hands it a fake Nuxt app instead, and a real vuex
// store with a stub history module serves `useStore()`.
const mounted = []

const mountHistory = ({ item, cancel, hasPermission = true }) => {
  const store = createStore({
    modules: {
      automationHistory: {
        namespaced: true,
        state: () => ({}),
        getters: { getNodeHistories: () => () => null },
        actions: {
          cancelWorkflowRun: (ctx, payload) => cancel(payload),
          fetchNodeHistories: () => {},
        },
      },
    },
  })
  const fakeNuxtApp = {
    $hasPermission: vi.fn(() => hasPermission),
    $i18n: { t: (key) => key },
    $registry: { getAll: () => ({}) },
  }
  const wrapper = mount(WorkflowHistory, {
    props: { item },
    global: {
      plugins: [store, { install: (app) => (app.$nuxt = fakeNuxtApp) }],
      provide: { workspace: ref({ id: 7 }), workflow: ref({ id: 3 }) },
      mocks: { $t: (key) => key },
      stubs: {
        Expandable: {
          template:
            '<div><slot name="header" :expanded="true" /><slot /></div>',
        },
        Icon: true,
        NodeHistory: true,
      },
    },
  })
  mounted.push(wrapper)
  return { wrapper, fakeNuxtApp }
}

const runningItem = (extra = {}) => ({
  id: 11,
  status: 'started',
  started_on: '2026-09-15T10:00:00Z',
  ...extra,
})

describe('WorkflowHistory cancellation', () => {
  afterEach(() => {
    // Unmount even when an assertion failed so the running-status timer is
    // always cleared.
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  test('dispatches the cancellation and disables the link while pending', async () => {
    let resolve
    const cancel = vi.fn(() => new Promise((r) => (resolve = r)))
    const { wrapper, fakeNuxtApp } = mountHistory({
      item: runningItem(),
      cancel,
    })
    const link = wrapper.find('.workflow-history__cancel-link')
    expect(link.exists()).toBe(true)
    expect(fakeNuxtApp.$hasPermission).toHaveBeenCalledWith(
      'automation.workflow.update',
      { id: 3 },
      7
    )

    await link.trigger('click')
    expect(cancel).toHaveBeenCalledWith({
      workflowId: 3,
      workflowHistoryId: 11,
    })
    expect(link.classes()).toContain('workflow-history__cancel-link--disabled')

    await link.trigger('click')
    expect(cancel).toHaveBeenCalledTimes(1)

    resolve()
    await flushPromises()
    expect(link.classes()).not.toContain(
      'workflow-history__cancel-link--disabled'
    )
  })

  test('shows the cancelling message instead of the link once requested', () => {
    const { wrapper } = mountHistory({
      item: runningItem({ cancellation_requested_on: '2026-09-15T10:00:05Z' }),
      cancel: vi.fn(),
    })
    expect(wrapper.find('.workflow-history__cancel-link').exists()).toBe(false)
    expect(wrapper.find('.workflow-history__cancel').text()).toBe(
      'historySidePanel.cancelling'
    )
  })

  test('hides the cancel link without the update permission', () => {
    const { wrapper } = mountHistory({
      item: runningItem(),
      cancel: vi.fn(),
      hasPermission: false,
    })
    expect(wrapper.find('.workflow-history__cancel').exists()).toBe(false)
  })

  test('hides the cancel link for finished runs and titles cancelled ones', () => {
    const { wrapper } = mountHistory({
      item: { id: 11, status: 'cancelled' },
      cancel: vi.fn(),
    })
    expect(wrapper.find('.workflow-history__cancel').exists()).toBe(false)
    expect(wrapper.find('.workflow-history__header-title').text()).toBe(
      'historySidePanel.statusCancelled'
    )
  })

  test('swallows the not-running error but notifies other errors', async () => {
    const notRunning = new Error('not running')
    notRunning.handler = {
      code: 'ERROR_AUTOMATION_WORKFLOW_HISTORY_NOT_RUNNING',
      notifyIf: vi.fn(),
    }
    const other = new Error('other')
    other.handler = { code: 'ERROR_OTHER', notifyIf: vi.fn() }
    const cancel = vi
      .fn()
      .mockRejectedValueOnce(notRunning)
      .mockRejectedValueOnce(other)
    const { wrapper } = mountHistory({ item: runningItem(), cancel })

    await wrapper.find('.workflow-history__cancel-link').trigger('click')
    await flushPromises()
    expect(notRunning.handler.notifyIf).not.toHaveBeenCalled()

    await wrapper.find('.workflow-history__cancel-link').trigger('click')
    await flushPromises()
    expect(other.handler.notifyIf).toHaveBeenCalledWith('automationWorkflow')
  })

  test('tells the user when somebody else already requested it', async () => {
    const alreadyRequested = new Error('already requested')
    alreadyRequested.handler = {
      code: 'ERROR_AUTOMATION_WORKFLOW_HISTORY_CANCELLATION_ALREADY_REQUESTED',
      notifyIf: vi.fn(),
    }
    const cancel = vi.fn().mockRejectedValue(alreadyRequested)
    const { wrapper } = mountHistory({ item: runningItem(), cancel })

    await wrapper.find('.workflow-history__cancel-link').trigger('click')
    await flushPromises()

    // The generic handler would show the backend's detail; this one gets a
    // message of its own so the user knows the request isn't theirs.
    expect(alreadyRequested.handler.notifyIf).toHaveBeenCalledWith(
      'automationWorkflow',
      expect.objectContaining({
        title: 'historySidePanel.cancellationAlreadyRequestedTitle',
        message: 'historySidePanel.cancellationAlreadyRequested',
      })
    )
    expect(
      wrapper.find('.workflow-history__cancel-link').classes()
    ).not.toContain('workflow-history__cancel-link--disabled')
  })
})
