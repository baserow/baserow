import { describe, expect, test } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatStepGroup from '@baserow/modules/core/components/chat/ChatStepGroup'
import tooltip from '@baserow/modules/core/directives/tooltip'
import { Registry } from '@baserow/modules/core/registry'
import {
  groupToolSteps,
  ToolPresentationType,
} from '@baserow/modules/core/toolPresentationTypes'

describe('ChatStepGroup', () => {
  test('renders a configured email action and its input through the same shared card', async () => {
    class EmailPresentation extends ToolPresentationType {
      static getType() {
        return 'send_email'
      }

      getActivity({ facts }, t) {
        return t(
          facts.delivery === 'sent' ? 'emailTool.sent' : 'emailTool.send'
        )
      }

      getInput({ input }) {
        return input
      }
    }
    const registry = new Registry()
    registry.registerNamespace('toolPresentation')
    registry.register('toolPresentation', new EmailPresentation())
    const t = (key) =>
      ({ 'emailTool.sent': 'Email sent', 'emailTool.send': 'Send email' })[
        key
      ] ?? key
    const [card] = groupToolSteps(
      [
        {
          id: 'email-1',
          tool: 'action_37',
          presentation_type: 'send_email',
          status: 'done',
          changes_data: true,
          input: {
            values: { to: 'alice@example.com', subject: 'Project update' },
          },
          facts: { delivery: 'sent' },
        },
      ],
      registry,
      t
    )
    const wrapper = mount(ChatStepGroup, {
      props: card,
      global: { directives: { tooltip }, mocks: { $t: t } },
    })

    expect(wrapper.get('.chat-step-group__title').text()).toBe('Email sent')
    expect(wrapper.get('.chat-step-group__status').text()).toBe(
      'toolPresentation.statusDone'
    )
    expect(wrapper.find('.iconoir-check-circle').exists()).toBe(true)
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('pre').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect(wrapper.get('pre').text()).toContain('alice@example.com')
    expect(wrapper.get('pre').text()).toContain('Project update')
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
  })

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
      global: { directives: { tooltip }, mocks: { $t: (key) => key } },
    })

    expect(wrapper.get('li').text()).toContain('Read rows')
    expect(wrapper.get('li').text()).toContain('toolPresentation.statusFailed')
    expect(wrapper.find('li .iconoir-warning-triangle').exists()).toBe(true)
    expect(wrapper.find('li .iconoir-check-circle').exists()).toBe(true)
    expect(wrapper.find('button .iconoir-check-circle').exists()).toBe(true)
    expect(wrapper.find('button .iconoir-warning-triangle').exists()).toBe(
      false
    )
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
    ['stopped', '.iconoir-minus-circle', 'toolPresentation.statusStopped'],
  ])(
    'shows the %s icon and accessible label for each expanded call',
    (status, icon, label) => {
      const wrapper = mount(ChatStepGroup, {
        props: {
          title: 'Workspace activity',
          status,
          lines: [{ id: 'a', title: 'Read rows', status }],
        },
        global: { directives: { tooltip }, mocks: { $t: (key) => key } },
      })

      expect(wrapper.get(`li ${icon}`).attributes('aria-hidden')).toBe('true')
      expect(wrapper.get('li .chat-step-group__status').text()).toContain(label)
      expect(wrapper.get('.chat-step-group__line-title').text()).toBe(
        'Read rows'
      )
    }
  )

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
      global: { directives: { tooltip }, mocks: { $t: (key) => key } },
    })

    expect(wrapper.get('button').attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('.iconoir-nav-arrow-right').exists()).toBe(true)
    expect(wrapper.find('pre').exists()).toBe(false)
    await wrapper.get('button').trigger('click')

    const detailsId = wrapper.get('button').attributes('aria-controls')
    expect(wrapper.get(`[id="${detailsId}"]`).text()).toContain(
      'toolPresentation.input'
    )
    expect(wrapper.get('pre').text()).toBe(JSON.stringify(values, null, 2))
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('pre').attributes('tabindex')).toBe('0')
    expect(wrapper.get('.chat-step-group__input-note').text()).toBe(
      'toolPresentation.inputTruncated'
    )

    await wrapper.setProps({ status: 'done', title: 'Added 1 row' })
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('pre').text()).toContain('Amount')
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('pre').exists()).toBe(false)
  })

  test.each([null, {}, { values: {} }, { values: [] }, { values: 'private' }])(
    'does not add a toggle for unavailable input: %j',
    (input) => {
      const wrapper = mount(ChatStepGroup, {
        props: { title: 'Added rows', status: 'done', input },
        global: { directives: { tooltip }, mocks: { $t: (key) => key } },
      })

      expect(wrapper.find('button').exists()).toBe(false)
      expect(wrapper.find('pre').exists()).toBe(false)
    }
  )

  test.each([false, true])(
    'shows an escaped failure hint on a header icon, expandable: %s',
    async (expandable) => {
      const failureHint = 'Tool failed: <img src=x onerror=alert(1)>'
      const wrapper = mount(ChatStepGroup, {
        props: {
          title: 'Create rows',
          status: 'failed',
          failureHint,
          input: expandable ? { values: { table_id: 42 } } : null,
        },
        global: { directives: { tooltip }, mocks: { $t: (key) => key } },
      })

      try {
        expect(wrapper.find('button button').exists()).toBe(false)
        expect(wrapper.get('.chat-step-group__status').text()).toContain(
          failureHint
        )
        await wrapper.get('.iconoir-warning-triangle').trigger('mouseenter')
        expect(document.querySelector('.tooltip__content').textContent).toBe(
          failureHint
        )
        expect(document.querySelector('.tooltip img')).toBeNull()

        await wrapper.setProps({ status: 'done' })
        expect(document.querySelector('.tooltip')).toBeNull()
        expect(wrapper.get('.chat-step-group__status').text()).not.toContain(
          failureHint
        )
      } finally {
        document.body.click()
        wrapper.unmount()
      }
    }
  )

  test('uses a generic failure hint when history has no reason', async () => {
    const wrapper = mount(ChatStepGroup, {
      props: { title: 'Read rows', status: 'failed' },
      global: { directives: { tooltip }, mocks: { $t: (key) => key } },
    })

    try {
      await wrapper.get('.iconoir-warning-triangle').trigger('mouseenter')
      expect(document.querySelector('.tooltip__content').textContent).toBe(
        'toolPresentation.failureFailed'
      )
      expect(wrapper.get('.chat-step-group__status').text()).toContain(
        'toolPresentation.failureFailed'
      )
    } finally {
      document.body.click()
      wrapper.unmount()
    }
  })

  test.each(['running', 'done', 'stopped'])(
    'does not show a failure tooltip for a %s call',
    async (status) => {
      const wrapper = mount(ChatStepGroup, {
        props: { title: 'Read rows', status, failureHint: 'Old failure' },
        global: { directives: { tooltip }, mocks: { $t: (key) => key } },
      })

      try {
        await wrapper.get('.chat-step-group__icon').trigger('mouseenter')
        expect(document.querySelector('.tooltip')).toBeNull()
        expect(wrapper.get('.chat-step-group__status').text()).not.toContain(
          'Old failure'
        )
      } finally {
        wrapper.unmount()
      }
    }
  )

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
      global: { directives: { tooltip }, mocks: { $t: (key) => key } },
    })

    try {
      await wrapper.get('button .chat-step-group__icon').trigger('mouseenter')
      expect(document.querySelector('.tooltip')).toBeNull()
      expect(
        wrapper.get('button .chat-step-group__status').text()
      ).not.toContain(failureHint)
      await wrapper.get('li .iconoir-warning-triangle').trigger('mouseenter')
      expect(document.querySelector('.tooltip__content').textContent).toBe(
        failureHint
      )
      expect(wrapper.get('li .chat-step-group__status').text()).toContain(
        failureHint
      )
    } finally {
      document.body.click()
      wrapper.unmount()
    }
  })

  test.each([
    ['running', '.chat-step-group__spinner', 'toolPresentation.statusRunning'],
    ['done', '.iconoir-check-circle', 'toolPresentation.statusDone'],
    ['failed', '.iconoir-warning-triangle', 'toolPresentation.statusFailed'],
    ['stopped', '.iconoir-minus-circle', 'toolPresentation.statusStopped'],
  ])('shows %s for a standalone action', (status, icon, label) => {
    const wrapper = mount(ChatStepGroup, {
      props: { title: 'Sending an email', status },
      global: { directives: { tooltip }, mocks: { $t: (key) => key } },
    })

    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find(icon).exists()).toBe(true)
    expect(wrapper.text()).toContain(label)
    expect(wrapper.attributes('aria-busy')).toBe(String(status === 'running'))
  })
})
