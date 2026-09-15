import { ref } from 'vue'
import { createStore } from 'vuex'
import { mount, flushPromises } from '@vue/test-utils'
import WorkflowHistory from '@baserow/modules/automation/components/workflow/sidePanels/WorkflowHistory'

// No module mocks: the component reads useNuxtApp() from the mounting Vue
// app's `$nuxt` first, so a tiny plugin hands it a fake Nuxt app, and a real
// vuex store with a stub history module serves useStore().
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
  return { wrapper, fakeNuxtApp }
}

const runningItem = (extra = {}) => ({
  id: 11,
  status: 'started',
  started_on: '2026-09-15T10:00:00Z',
  ...extra,
})

describe('WorkflowHistory cancellation', () => {
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
    wrapper.unmount()
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
    wrapper.unmount()
  })

  test('hides the cancel link without the update permission', () => {
    const { wrapper } = mountHistory({
      item: runningItem(),
      cancel: vi.fn(),
      hasPermission: false,
    })
    expect(wrapper.find('.workflow-history__cancel').exists()).toBe(false)
    wrapper.unmount()
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
    wrapper.unmount()
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
    wrapper.unmount()
  })
})
