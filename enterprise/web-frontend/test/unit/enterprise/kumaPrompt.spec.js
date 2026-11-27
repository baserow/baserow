import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { useNuxtApp } from '#app'
import { afterEach, expect, test, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import KumaContextButton from '@baserow_enterprise/components/assistant/KumaContextButton'
import AssistantEditorSession from '@baserow_enterprise/components/assistant/AssistantEditorSession'

const { runAction } = vi.hoisted(() => ({ runAction: vi.fn() }))
vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: () => ({ runAction }),
}))
vi.mock('@baserow_enterprise/utils/assistant', () => ({
  isAssistantAvailable: () => true,
}))

const { kumaPrompt } = JSON.parse(
  readFileSync(
    resolve(
      process.cwd(),
      '../enterprise/web-frontend/modules/baserow_enterprise/locales/en.json'
    ),
    'utf8'
  )
)
let wrapper
afterEach(() => {
  wrapper?.unmount()
  runAction.mockReset()
  vi.restoreAllMocks()
})

async function mount({
  enabled = true,
  blockedMessage = '',
  action = 'generate_formula',
} = {}) {
  const draft = ref('1')
  const host = defineComponent({
    setup() {
      const { target } = useNuxtApp().$kumaEditor
      return () =>
        h('div', [
          h(KumaContextButton, {
            enabled,
            blockedMessage,
            workspace: { id: 5 },
            title: 'Database formula',
            label: 'Total',
            placeholder: 'What should this field calculate?',
            action,
            parameters: { table_id: 7, current: draft.value },
            onCompleted: (result) => {
              draft.value = result.formula
            },
          }),
          target.value &&
            h(AssistantEditorSession, {
              key: target.value.id,
              target: target.value,
            }),
        ])
    },
  })
  wrapper = await mountSuspended(host)
  return draft
}

async function open() {
  await wrapper.get('.kuma-context-button').trigger('click')
  await flushPromises()
  return wrapper.get('textarea')
}

test('only shows an accessible icon until the editor is attached', async () => {
  await mount()
  const button = wrapper.get('.kuma-context-button')
  expect(button.attributes('aria-label')).toBe(
    'kumaPrompt.generate_formulaTooltip'
  )
  expect(button.text()).toBe('')
  expect(wrapper.find('textarea').exists()).toBe(false)
  const input = await open()
  expect(input.element.value).toBe('kumaPrompt.generate_formulaStarter ')
  expect(input.element.selectionStart).toBe(input.element.value.length)
  expect(wrapper.get('.assistant__send-button').element.disabled).toBe(true)
  await input.trigger('keydown', { key: 'Enter' })
  expect(runAction).not.toHaveBeenCalled()
  expect(button.attributes('aria-pressed')).toBe('true')
  expect(wrapper.get('.assistant-editor__chip').text()).toContain(
    'Database formula · Total'
  )
  await wrapper.get('.assistant-editor__chip button').trigger('click')
  expect(wrapper.find('textarea').exists()).toBe(false)
})

test.each([
  ['generate_formula', 'Calculate', 'the total price including tax'],
  ['edit_view_filters', 'Show rows', 'where name contains davide'],
  ['create_view', 'Create a view', 'of tasks sorted by due date'],
  ['generate_agent_instructions', 'This Agent should', 'summarize new orders'],
  ['update_service_filters', 'Return rows', 'where stock is below five'],
  ['create_table', 'Create a table', 'for tracking book loans'],
  ['create_database', 'Create a database', 'with events and registrations'],
  [
    'generate_ai_field_prompt',
    'For each row,',
    'summarize the customer feedback',
  ],
  ['add_row_color', 'Highlight rows', 'where the deadline has passed in red'],
])(
  'can continue the %s starter without editing it',
  async (action, starter, continuation) => {
    vi.spyOn(useNuxtApp().$i18n, 't').mockImplementation(
      (key) => kumaPrompt[key.split('.')[1]] ?? key
    )
    await mount({ action })
    const input = await open()
    expect(input.element.value).toBe(starter + ' ')
    expect(input.element.selectionStart).toBe(input.element.value.length)
    expect(input.element.selectionEnd).toBe(input.element.value.length)
    await input.trigger('keydown', { key: 'Enter' })
    expect(runAction).not.toHaveBeenCalled()
    runAction.mockResolvedValue({ result: {} })
    await input.setValue(input.element.value + continuation)
    await input.trigger('keydown', { key: 'Enter' })
    expect(runAction).toHaveBeenCalledWith(
      action,
      starter + ' ' + continuation,
      { table_id: 7, current: '1' },
      5
    )
  }
)

test('sends the latest local draft and workspace on each revision', async () => {
  const draft = await mount()
  const input = await open()
  runAction.mockResolvedValue({ result: { formula: '2' } })
  await input.setValue(' Double it ')
  await input.trigger('keydown', { key: 'Enter', shiftKey: true })
  expect(runAction).not.toHaveBeenCalled()
  await input.trigger('keydown', { key: 'Enter' })
  await flushPromises()
  expect(draft.value).toBe('2')
  expect(wrapper.get('[role=log]').text()).toContain(
    'kumaPrompt.formulaDraftUpdated'
  )
  expect(wrapper.get('[role=log]').text()).not.toContain(draft.value)
  await input.setValue('Double it again')
  await wrapper.get('.assistant__send-button').trigger('click')
  await flushPromises()
  expect(runAction.mock.calls).toEqual([
    ['generate_formula', 'Double it', { table_id: 7, current: '1' }, 5],
    ['generate_formula', 'Double it again', { table_id: 7, current: '2' }, 5],
  ])
})

test.each(['edit', 'detach'])(
  'preserves the draft after a concurrent %s',
  async (change) => {
    const draft = await mount()
    let finish
    runAction.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const input = await open()
    await input.setValue('Replace it')
    await input.trigger('keydown', { key: 'Enter' })
    if (change === 'edit') draft.value = '3'
    else await wrapper.get('.assistant-editor__chip button').trigger('click')
    await flushPromises()
    finish({ result: { formula: '99' } })
    await flushPromises()
    expect(draft.value).toBe(change === 'edit' ? '3' : '1')
    if (change === 'edit')
      expect(wrapper.get('[role=status]').text()).toContain(
        'kumaPrompt.draftChanged'
      )
  }
)

test('shows the reason a request is blocked', async () => {
  await mount({ blockedMessage: 'Save first.' })
  const input = await open()
  await input.setValue('Change it')
  expect(wrapper.get('[role=status]').text()).toBe('Save first.')
  expect(wrapper.get('.assistant__send-button').element.disabled).toBe(true)
  await input.trigger('keydown', { key: 'Enter' })
  expect(runAction).not.toHaveBeenCalled()
})

test('hides a disabled entry point', async () => {
  await mount({ enabled: false })
  expect(wrapper.find('button').exists()).toBe(false)
})
