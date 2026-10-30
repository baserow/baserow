import { describe, expect, test } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatStepGroup from '@baserow/modules/core/components/chat/ChatStepGroup'
import { Registry } from '@baserow/modules/core/registry'
import {
  groupToolSteps,
  ToolPresentationType,
} from '@baserow/modules/core/toolPresentationTypes'

describe('ChatStepGroup', () => {
  test('renders a configured email action through the same shared card', () => {
    class EmailPresentation extends ToolPresentationType {
      static getType() {
        return 'send_email'
      }

      getActivity({ facts }, t) {
        return t(
          facts.delivery === 'sent' ? 'emailTool.sent' : 'emailTool.send'
        )
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
          facts: { delivery: 'sent' },
        },
      ],
      registry,
      t
    )
    const wrapper = mount(ChatStepGroup, {
      props: card,
      global: { mocks: { $t: t } },
    })

    expect(wrapper.get('.chat-step-group__title').text()).toBe('Email sent')
    expect(wrapper.get('.chat-step-group__status').text()).toBe(
      'toolPresentation.statusDone'
    )
    expect(wrapper.find('.iconoir-check-circle').exists()).toBe(true)
    expect(wrapper.find('button').exists()).toBe(false)
  })

  test('shows grouped details by default and can collapse and expand them', async () => {
    const wrapper = mount(ChatStepGroup, {
      props: {
        title: 'Looked at your workspace',
        status: 'failed',
        lines: [{ id: 'a', title: 'Reading tables', status: 'failed' }],
      },
      global: { mocks: { $t: (key) => key } },
    })

    expect(wrapper.get('li').text()).toContain('Reading tables')
    expect(wrapper.get('li').text()).toContain('toolPresentation.statusFailed')
    expect(wrapper.find('li .iconoir-warning-triangle').exists()).toBe(false)
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('button .iconoir-nav-arrow-down').exists()).toBe(true)
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('ul').exists()).toBe(false)
    expect(wrapper.get('button').attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('button .iconoir-nav-arrow-right').exists()).toBe(true)
    await wrapper.get('button').trigger('click')
    expect(wrapper.get('li').text()).toContain('Reading tables')
  })

  test.each([
    ['running', '.chat-step-group__spinner', 'toolPresentation.statusRunning'],
    ['done', '.iconoir-check-circle', 'toolPresentation.statusDone'],
    ['failed', '.iconoir-warning-triangle', 'toolPresentation.statusFailed'],
    ['stopped', '.iconoir-minus-circle', 'toolPresentation.statusStopped'],
  ])('shows %s for a standalone action', (status, icon, label) => {
    const wrapper = mount(ChatStepGroup, {
      props: { title: 'Sending an email', status },
      global: { mocks: { $t: (key) => key } },
    })

    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find(icon).exists()).toBe(true)
    expect(wrapper.text()).toContain(label)
    expect(wrapper.attributes('aria-busy')).toBe(String(status === 'running'))
  })
})
