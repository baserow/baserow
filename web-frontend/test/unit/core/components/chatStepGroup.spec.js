import { describe, expect, test } from 'vitest'
import { mount } from '@vue/test-utils'
import autoOverflowScroll from '@baserow/modules/core/directives/autoOverflowScroll'
import ChatStepGroup from '@baserow/modules/core/components/chat/ChatStepGroup'

const global = {
  directives: { autoOverflowScroll },
  mocks: { $t: (key) => key },
}

describe('ChatStepGroup', () => {
  test('shows grouped details by default and can collapse and expand them', async () => {
    const wrapper = mount(ChatStepGroup, {
      props: {
        title: 'Looked at your workspace',
        status: 'done',
        lines: [
          { id: 'a', title: 'Read rows', status: 'failed' },
          { id: 'b', title: 'Read 22 rows from Projects', status: 'done' },
        ],
      },
      global,
    })

    expect(wrapper.get('li').text()).toContain('Read rows')
    expect(wrapper.get('li').text()).toContain('toolPresentation.statusFailed')
    expect(wrapper.find('li .iconoir-warning-triangle').exists()).toBe(true)
    expect(wrapper.find('li .iconoir-check-circle').exists()).toBe(true)
    expect(wrapper.find('button .iconoir-check-circle').exists()).toBe(true)
    expect(
      wrapper
        .find('.chat-step-group__header .iconoir-warning-triangle')
        .exists()
    ).toBe(false)
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('button .iconoir-nav-arrow-down').exists()).toBe(true)
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('ul').exists()).toBe(false)
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('button .iconoir-nav-arrow-right').exists()).toBe(true)
    await wrapper.get('button').trigger('click')
    expect(wrapper.get('li').text()).toContain('Read rows')
    expect(wrapper.find('li .iconoir-warning-triangle').exists()).toBe(true)
  })

  test.each([
    ['running', '.chat-step-group__spinner', 'toolPresentation.statusRunning'],
    ['done', '.iconoir-check-circle', 'toolPresentation.statusDone'],
    ['failed', '.iconoir-warning-triangle', 'toolPresentation.statusFailed'],
    ['stopped', '.iconoir-minus-circle', 'toolPresentation.statusInterrupted'],
    ['waiting', '.iconoir-clock', 'toolPresentation.statusWaiting'],
    ['rejected', '.iconoir-prohibition', 'toolPresentation.statusRejected'],
  ])(
    'shows the %s icon and accessible label for each expanded call',
    (status, icon, label) => {
      const wrapper = mount(ChatStepGroup, {
        props: {
          title: 'Workspace activity',
          status,
          lines: [{ id: 'a', title: 'Read rows', status }],
        },
        global,
      })

      expect(wrapper.get(`li ${icon}`).attributes('aria-hidden')).toBe('true')
      expect(
        wrapper
          .get(
            status === 'failed'
              ? 'li .chat-tool-failure'
              : 'li .chat-step-group__status'
          )
          .text()
      ).toContain(label)
      expect(wrapper.get('.chat-step-group__line-title').text()).toBe(
        'Read rows'
      )
    }
  )

  test('running and completed labels stay visible on grouped calls and their header', async () => {
    const wrapper = mount(ChatStepGroup, {
      props: {
        title: 'Read the workspace',
        status: 'running',
        lines: [
          { id: 'a', title: 'List tables', status: 'done' },
          { id: 'b', title: 'Read rows', status: 'running' },
        ],
      },
      global,
    })
    expect(
      wrapper
        .findAll('.chat-step-group__status--visible')
        .map((label) => label.text())
    ).toEqual([
      'toolPresentation.statusRunning',
      'toolPresentation.statusDone',
      'toolPresentation.statusRunning',
    ])
    await wrapper.setProps({
      title: 'Updated a row',
      status: 'done',
      lines: [],
    })
    expect(wrapper.get('.chat-step-group__status--visible').text()).toBe(
      'toolPresentation.statusDone'
    )
  })

  test('says that an interrupted change may have completed', () => {
    const card = (changesData) =>
      mount(ChatStepGroup, {
        props: { title: 'Create rows', status: 'stopped', changesData },
        global,
      })

    expect(card(true).get('.chat-step-group__status--visible').text()).toBe(
      'toolPresentation.statusStopped'
    )
    expect(card(false).find('.chat-step-group__status--visible').exists()).toBe(
      false
    )
  })

  test('expands input safely, indicates a shortened preview, and keeps it open through completion', async () => {
    const values = {
      table_id: 42,
      rows: [{ Name: '<img src=x onerror=alert(1)>', Done: false, Amount: 0 }],
    }
    const wrapper = mount(ChatStepGroup, {
      props: {
        title: 'Creating rows',
        status: 'running',
        input: { values, truncated: true },
      },
      global,
    })

    expect(wrapper.get('button').attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('.iconoir-nav-arrow-right').exists()).toBe(true)
    expect(wrapper.find('pre').exists()).toBe(false)
    await wrapper.get('button').trigger('click')

    const detailsId = wrapper.get('button').attributes('aria-controls')
    expect(wrapper.get(`[id="${detailsId}"]`).text()).toContain(
      'toolPresentation.input'
    )
    const rows = wrapper.findAll('.chat-tool-input__table tr')
    expect(rows.map((row) => row.get('th').text())).toEqual([
      'table_id',
      'rows',
    ])
    expect(rows[1].get('pre').text()).toBe(JSON.stringify(values.rows, null, 2))
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('.chat-tool-input__values').attributes('tabindex')).toBe(
      '0'
    )
    expect(wrapper.get('.chat-tool-input__note').text()).toBe(
      'toolPresentation.inputTruncated'
    )

    await wrapper.setProps({ status: 'done', title: 'Added 1 row' })
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.chat-tool-input__table').text()).toContain('Amount')
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('.chat-tool-input').exists()).toBe(false)
  })

  test('does not add a toggle without input', () => {
    const wrapper = mount(ChatStepGroup, {
      props: { title: 'Added rows', status: 'done', input: null },
      global,
    })

    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('pre').exists()).toBe(false)
  })

  test.each([false, true])(
    'opens the failure context on activation, expandable: %s',
    async (expandable) => {
      const failureHint = 'Tool failed: <img src=x onerror=alert(1)>'
      const wrapper = mount(ChatStepGroup, {
        attachTo: document.body,
        props: {
          title: 'Create rows',
          status: 'failed',
          failureHint,
          input: expandable ? { values: { table_id: 42 } } : null,
        },
        global,
      })
      try {
        const badge = wrapper.get('.chat-tool-failure')
        expect(wrapper.find('button button').exists()).toBe(false)
        await badge.trigger('mouseenter')
        await badge.trigger('focus')
        expect(badge.attributes('aria-expanded')).toBe('false')
        expect(wrapper.text()).not.toContain(failureHint)
        await badge.trigger('click')
        const panel = wrapper.get('[role="dialog"]')
        expect(panel.attributes('id')).toBe(badge.attributes('aria-controls'))
        expect(badge.attributes('aria-expanded')).toBe('true')
        expect(panel.text()).toBe(failureHint)
        expect(panel.find('img').exists()).toBe(false)
        if (expandable) {
          expect(
            wrapper.get('.chat-step-group__header').attributes('aria-expanded')
          ).toBe('false')
        }
        await wrapper.setProps({ failureHint: 'Public error' })
        expect(badge.attributes('aria-expanded')).toBe('false')
        expect(wrapper.text()).not.toContain(failureHint)
        await badge.trigger('click')
        const currentPanel = wrapper.get('[role="dialog"]')
        expect(currentPanel.text()).toBe('Public error')
        await currentPanel.trigger('keydown.esc')
        expect(badge.attributes('aria-expanded')).toBe('false')
        expect(document.activeElement).toBe(badge.element)
        await badge.trigger('click')
        document.body.click()
        await wrapper.vm.$nextTick()
        expect(badge.attributes('aria-expanded')).toBe('false')
        await wrapper.setProps({ status: 'done' })
        expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
      } finally {
        wrapper.unmount()
      }
    }
  )

  test('uses a generic explanation when history has no reason', async () => {
    const wrapper = mount(ChatStepGroup, {
      props: { title: 'Read rows', status: 'failed' },
      global,
    })
    try {
      await wrapper.get('.chat-tool-failure').trigger('click')
      expect(wrapper.get('[role="dialog"]').text()).toBe(
        'toolPresentation.failureFailed'
      )
    } finally {
      wrapper.unmount()
    }
  })

  test('opening another failed call dismisses the previous error', async () => {
    const wrapper = mount(ChatStepGroup, {
      attachTo: document.body,
      props: {
        title: 'Read rows',
        status: 'failed',
        failureHint: 'Last call failed',
        lines: [
          {
            id: 'a',
            title: 'Read schema',
            status: 'failed',
            failureHint: 'Schema missing',
          },
        ],
      },
      global,
    })
    try {
      const [summary, line] = wrapper.findAll('.chat-tool-failure')
      await summary.trigger('click')
      await line.trigger('click')
      expect(summary.attributes('aria-expanded')).toBe('false')
      expect(line.attributes('aria-expanded')).toBe('true')
    } finally {
      wrapper.unmount()
    }
  })

  test('explains an earlier failed call without attaching its hint to a successful summary', async () => {
    const failureHint = 'The requested table was not found in this workspace.'
    const wrapper = mount(ChatStepGroup, {
      props: {
        title: 'Looked at your workspace',
        status: 'done',
        lines: [
          { id: 'a', title: 'Read rows', status: 'failed', failureHint },
          { id: 'b', title: 'Read 22 rows', status: 'done' },
        ],
      },
      global,
    })

    try {
      expect(
        wrapper
          .get('.chat-step-group__heading')
          .find('.chat-tool-failure')
          .exists()
      ).toBe(false)
      const failed = wrapper.get('li .chat-tool-failure')
      await failed.trigger('click')
      expect(wrapper.get('.chat-tool-failure__reason').text()).toBe(failureHint)
    } finally {
      document.body.click()
      wrapper.unmount()
    }
  })

  test.each([
    ['running', '.chat-step-group__spinner', 'toolPresentation.statusRunning'],
    ['done', '.iconoir-check-circle', 'toolPresentation.statusDone'],
    ['failed', '.iconoir-warning-triangle', 'toolPresentation.statusFailed'],
    ['stopped', '.iconoir-minus-circle', 'toolPresentation.statusInterrupted'],
    ['waiting', '.iconoir-clock', 'toolPresentation.statusWaiting'],
    ['rejected', '.iconoir-prohibition', 'toolPresentation.statusRejected'],
  ])('shows %s for a standalone action', (status, icon, label) => {
    const wrapper = mount(ChatStepGroup, {
      props: { title: 'Sending an email', status },
      global,
    })

    expect(wrapper.find('.chat-step-group__header--toggle').exists()).toBe(
      false
    )
    expect(wrapper.find(icon).exists()).toBe(true)
    expect(wrapper.text()).toContain(label)
    expect(wrapper.attributes('aria-busy')).toBe(String(status === 'running'))
  })

  test('a done call with failed items warns and lists them in the details', async () => {
    const wrapper = mount(ChatStepGroup, {
      props: {
        title: 'Created 1 field',
        status: 'done',
        itemErrors: [
          { item: 'Total', message: "The formula isn't valid." },
          { item: '', message: 'Unnamed item failed.' },
        ],
      },
      global,
    })

    expect(wrapper.find('button .iconoir-warning-circle').exists()).toBe(true)
    expect(wrapper.find('button .iconoir-check-circle').exists()).toBe(false)
    expect(wrapper.get('.chat-step-group__status--visible').text()).toBe(
      'toolPresentation.statusPartial'
    )
    await wrapper.get('button').trigger('click')
    const errors = wrapper.findAll('.chat-step-group__item-error')
    expect(errors.map((error) => error.text())).toEqual([
      "Total The formula isn't valid.",
      'Unnamed item failed.',
    ])
    expect(wrapper.find('.chat-step-group__item-error-name').text()).toBe(
      'Total'
    )
  })
})
