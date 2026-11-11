import { ref } from 'vue'
import { createStore } from 'vuex'
import { mount, flushPromises } from '@vue/test-utils'
import Badge from '@baserow/modules/core/components/Badge'
import WorkflowHistory from '@baserow/modules/automation/components/workflow/sidePanels/WorkflowHistory'

// Mounted on a fresh Vue app rather than through TestApp/mountSuspended on
// purpose: the component reads `useNuxtApp().$hasPermission`, which Nuxt defines
// on the real test app as a non-configurable getter, so it can't be spied or
// overridden per test. `useNuxtApp()` resolves the mounting Vue app's `$nuxt`
// first, so a tiny plugin hands it a fake Nuxt app instead, and a real vuex
// store with a stub history module serves `useStore()`.
const mounted = []

// `nodeHistories` fills the store for the expanded run. `nodeType` renders the
// real NodeHistory rows with that type; without it they stay stubbed.
const mountHistory = ({
  item,
  cancel = vi.fn(),
  fetchNodeHistories = vi.fn(),
  hasPermission = true,
  nodeHistories = null,
  nodeType = null,
  t = (key) => key,
}) => {
  const store = createStore({
    modules: {
      automationHistory: {
        namespaced: true,
        state: () => ({}),
        getters: {
          getNodeHistories: () => () => nodeHistories,
          getNodeResult: () => () => null,
        },
        actions: {
          cancelWorkflowRun: (ctx, payload) => cancel(payload),
          fetchNodeHistories: (ctx, payload) => fetchNodeHistories(payload),
          fetchNodeResult: () => {},
        },
      },
    },
  })
  const fakeNuxtApp = {
    $hasPermission: vi.fn(() => hasPermission),
    $i18n: { t },
    $registry: { getAll: () => ({}), get: () => nodeType },
  }
  const wrapper = mount(WorkflowHistory, {
    props: { item },
    global: {
      plugins: [store, { install: (app) => (app.$nuxt = fakeNuxtApp) }],
      provide: { workspace: ref({ id: 7 }), workflow: ref({ id: 3 }) },
      components: { Badge },
      mocks: { $t: (key) => key },
      stubs: {
        Expandable: {
          name: 'Expandable',
          emits: ['toggle'],
          template:
            '<div><slot name="header" :expanded="true" /><slot /></div>',
        },
        Icon: true,
        Context: true,
        Button: true,
        SampleDataModal: true,
        ...(nodeType ? {} : { NodeHistory: true }),
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

describe('WorkflowHistory passes', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  const nodeType = {
    iconClass: 'iconoir-globe',
    getHistoryLabel: ({ nodeHistory }) => nodeHistory.node_label,
  }
  const attempt = (extra) => ({
    node: 5,
    node_type: 'http_request',
    node_label: 'Fetch',
    iteration_path: '',
    parent_node_id: null,
    message: '',
    ...extra,
  })

  test('numbers the passes of a node by its first attempts only', () => {
    // The node ran twice (a jump looped back to it); its first pass was
    // retried once. The retry belongs to the first pass, so the node still
    // counts two passes and the retry takes the number of its pass.
    const { wrapper } = mountHistory({
      item: {
        id: 11,
        status: 'success',
        started_on: '2026-09-15T10:00:00Z',
        completed_on: '2026-09-15T10:00:02Z',
      },
      nodeHistories: [
        attempt({ id: 1, attempt: 1, status: 'retried' }),
        attempt({ id: 2, attempt: 2, status: 'success' }),
        attempt({ id: 3, attempt: 1, status: 'success' }),
      ],
      nodeType,
      t: (key, params) =>
        params?.n !== undefined ? `${key}:${params.n}` : key,
    })

    expect(
      wrapper.findAll('.node-history__header-info-pass').map((el) => el.text())
    ).toEqual([
      'historySidePanel.runNumber:1',
      'historySidePanel.runNumber:1',
      'historySidePanel.retryNumber:1',
      'historySidePanel.runNumber:2',
    ])
  })

  test('a node that only ran once shows no pass, retried or not', () => {
    const { wrapper } = mountHistory({
      item: {
        id: 11,
        status: 'success',
        started_on: '2026-09-15T10:00:00Z',
        completed_on: '2026-09-15T10:00:02Z',
      },
      nodeHistories: [
        attempt({ id: 1, attempt: 1, status: 'retried' }),
        attempt({ id: 2, attempt: 2, status: 'success' }),
      ],
      nodeType,
      t: (key, params) =>
        params?.n !== undefined ? `${key}:${params.n}` : key,
    })

    expect(
      wrapper.findAll('.node-history__header-info-pass').map((el) => el.text())
    ).toEqual(['historySidePanel.retryNumber:1'])
  })
})

describe('WorkflowHistory runs in progress', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  const nodeType = {
    iconClass: 'iconoir-timer',
    getHistoryLabel: ({ nodeHistory }) => nodeHistory.node_label,
  }
  const attempt = (extra) => ({
    node: 5,
    node_type: 'wait',
    node_label: 'Wait',
    attempt: 1,
    iteration_path: '',
    parent_node_id: null,
    message: '',
    ...extra,
  })

  test('shows the node histories of a running run next to the cancel link', () => {
    // The node rows of a run in progress are shown so that a waiting node can
    // be seen; the run keeps its running timer and cancel link.
    const { wrapper } = mountHistory({
      item: runningItem(),
      nodeHistories: [
        attempt({
          id: 1,
          status: 'waiting',
          resume_at: '2026-09-15T10:01:00Z',
        }),
      ],
      nodeType,
    })

    expect(wrapper.findAll('.node-history__header-row')).toHaveLength(1)
    expect(wrapper.find('.badge').text()).toBe(
      'historySidePanel.statusWaitingBadge'
    )
    expect(wrapper.find('.workflow-history__run-time').exists()).toBe(true)
    expect(wrapper.find('.workflow-history__cancel-link').exists()).toBe(true)
  })

  test('fetches the node histories of a running run when it is expanded', async () => {
    const fetchNodeHistories = vi.fn()
    const { wrapper } = mountHistory({
      item: runningItem(),
      fetchNodeHistories,
    })
    expect(fetchNodeHistories).not.toHaveBeenCalled()

    await wrapper.findComponent({ name: 'Expandable' }).vm.$emit('toggle')

    expect(fetchNodeHistories).toHaveBeenCalledWith({ workflowHistoryId: 11 })
  })

  test('fetches the node histories again once the run completes', async () => {
    // The rows shown while the run was in progress stopped at a waiting or
    // running node, so they are fetched afresh rather than served from cache.
    const fetchNodeHistories = vi.fn()
    const { wrapper } = mountHistory({
      item: runningItem(),
      fetchNodeHistories,
      nodeHistories: [],
    })
    expect(fetchNodeHistories).not.toHaveBeenCalled()

    await wrapper.setProps({
      item: runningItem({
        status: 'success',
        completed_on: '2026-09-15T10:00:05Z',
      }),
    })

    expect(fetchNodeHistories).toHaveBeenCalledTimes(1)
    expect(fetchNodeHistories).toHaveBeenCalledWith({
      workflowHistoryId: 11,
      refresh: true,
    })
  })
})
