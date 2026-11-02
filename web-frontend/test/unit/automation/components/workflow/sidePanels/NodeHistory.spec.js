import { createStore } from 'vuex'
import { mount } from '@vue/test-utils'
import moment from '@baserow/modules/core/moment'
import { getUserTimeZone } from '@baserow/modules/core/utils/date'
import Badge from '@baserow/modules/core/components/Badge'
import NodeHistory from '@baserow/modules/automation/components/workflow/sidePanels/NodeHistory'

// Mounted on a fresh Vue app with a fake Nuxt app, like WorkflowHistory.spec.js
// next to it: the component reads the node type from `useNuxtApp().$registry`
// and the labels from `$i18n`, both of which are driven per test this way.
const mounted = []

const nodeType = {
  iconClass: 'iconoir-globe',
  getHistoryLabel: ({ nodeHistory }) => nodeHistory.node_label,
}

const mountNodeHistory = (nodeHistory, props = {}) => {
  const store = createStore({
    modules: {
      automationHistory: {
        namespaced: true,
        state: () => ({}),
        getters: { getNodeResult: () => () => null },
        actions: { fetchNodeResult: () => {} },
      },
    },
  })
  const fakeNuxtApp = {
    // Echoes the number (or time) so the assertions see which label is used.
    $i18n: {
      t: (key, params) => {
        const value = params?.n ?? params?.time
        return value !== undefined ? `${key}:${value}` : key
      },
    },
    $registry: { get: () => nodeType },
  }
  const wrapper = mount(NodeHistory, {
    props: { workflowHistoryId: 11, nodeHistory, ...props },
    global: {
      plugins: [store, { install: (app) => (app.$nuxt = fakeNuxtApp) }],
      components: { Badge },
      mocks: { $t: (key) => key },
      stubs: {
        Expandable: {
          template:
            '<div><slot name="header" :expanded="false" /><slot /></div>',
        },
        Icon: true,
        Context: true,
        Button: true,
        SampleDataModal: true,
      },
    },
  })
  mounted.push(wrapper)
  return wrapper
}

const attempt = (extra = {}) => ({
  id: 1,
  node: 5,
  node_type: 'http_request',
  node_label: 'Fetch',
  status: 'success',
  attempt: 1,
  iteration_path: '',
  parent_node_id: null,
  message: '',
  ...extra,
})

const labels = (wrapper) =>
  wrapper.findAll('.node-history__header-info-pass').map((el) => el.text())

describe('NodeHistory attempts', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  test('a retried attempt is badged and says why it was retried', () => {
    const wrapper = mountNodeHistory(
      attempt({
        status: 'retried',
        attempt: 2,
        message: 'Retry 2 of 2 scheduled. Connection reset',
      })
    )

    const badge = wrapper.find('.badge')
    expect(badge.text()).toBe('historySidePanel.statusRetriedBadge')
    expect(badge.classes()).toContain('badge--yellow')
    expect(labels(wrapper)).toEqual(['historySidePanel.retryNumber:1'])
    expect(wrapper.find('.node-history__error-info').text()).toBe(
      'Retry 2 of 2 scheduled. Connection reset'
    )
  })

  test('the first attempt is the normal run and carries no retry label', () => {
    const wrapper = mountNodeHistory(
      attempt({
        status: 'retried',
        attempt: 1,
        message: 'Retry 1 of 2 scheduled. Connection reset',
      })
    )

    expect(labels(wrapper)).toEqual([])
    expect(wrapper.find('.node-history__error-info').text()).toBe(
      'Retry 1 of 2 scheduled. Connection reset'
    )
  })

  test('a successful attempt shows no message', () => {
    const wrapper = mountNodeHistory(attempt())

    const badge = wrapper.find('.badge')
    expect(badge.text()).toBe('historySidePanel.statusSuccessBadge')
    expect(badge.classes()).toContain('badge--green')
    expect(labels(wrapper)).toEqual([])
    expect(wrapper.find('.node-history__error').exists()).toBe(false)
  })

  test('the attempt that failed for good is an error', () => {
    const wrapper = mountNodeHistory(
      attempt({
        status: 'error',
        attempt: 3,
        message: 'Failed after 2 retries. Connection reset',
      })
    )

    const badge = wrapper.find('.badge')
    expect(badge.text()).toBe('historySidePanel.statusErrorBadge')
    expect(badge.classes()).toContain('badge--red')
    expect(labels(wrapper)).toEqual(['historySidePanel.retryNumber:2'])
    expect(wrapper.find('.node-history__error-info').text()).toBe(
      'Failed after 2 retries. Connection reset'
    )
  })

  test('the pass of the node comes before the retry', () => {
    const wrapper = mountNodeHistory(
      attempt({ id: 7, status: 'retried', attempt: 2, message: 'Retrying' }),
      { passInfoByHistoryId: { 7: { pass: 2, total: 2 } } }
    )

    expect(labels(wrapper)).toEqual([
      'historySidePanel.runNumber:2',
      'historySidePanel.retryNumber:1',
    ])
  })
})

describe('NodeHistory of a run in progress', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  test('a waiting node says until when it waits, in the local time zone', () => {
    const resumeAt = '2026-09-15T10:00:30Z'
    const wrapper = mountNodeHistory(
      attempt({ node_type: 'wait', status: 'waiting', resume_at: resumeAt })
    )

    const badge = wrapper.find('.badge')
    expect(badge.text()).toBe('historySidePanel.statusWaitingBadge')
    expect(badge.classes()).toContain('badge--cyan')
    const expected = moment.utc(resumeAt).tz(getUserTimeZone())
    expect(labels(wrapper)).toEqual([
      `historySidePanel.waitingUntil:${expected.format('HH:mm:ss')}`,
    ])
    // The full date is one hover away, for a wait that crosses midnight.
    expect(
      wrapper.find('.node-history__header-info-pass').attributes('title')
    ).toBe(expected.format('YYYY-MM-DD HH:mm:ss'))
    expect(wrapper.find('.node-history__error').exists()).toBe(false)
    // Nothing to show yet: the result only exists once the wait is over.
    expect(wrapper.find('.node-history__header-show-result').exists()).toBe(
      false
    )
  })

  test('a node that is running right now is badged as such', () => {
    const wrapper = mountNodeHistory(attempt({ status: 'started' }))

    const badge = wrapper.find('.badge')
    expect(badge.text()).toBe('historySidePanel.statusRunningBadge')
    expect(badge.classes()).toContain('badge--cyan')
    expect(labels(wrapper)).toEqual([])
    expect(wrapper.find('.node-history__header-show-result').exists()).toBe(
      false
    )
  })

  test('a node the run was stopped at is badged as cancelled', () => {
    const wrapper = mountNodeHistory(
      attempt({ node_type: 'wait', status: 'cancelled' })
    )

    const badge = wrapper.find('.badge')
    expect(badge.text()).toBe('historySidePanel.statusCancelledBadge')
    expect(badge.classes()).toContain('badge--neutral')
    expect(labels(wrapper)).toEqual([])
  })

  test('a finished node keeps its result toggle', () => {
    const wrapper = mountNodeHistory(attempt())
    expect(wrapper.find('.node-history__header-show-result').exists()).toBe(
      true
    )
  })
})
