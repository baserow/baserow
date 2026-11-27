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
vi.mock('@baserow_enterprise/utils/assistant', async (importOriginal) => ({
  ...(await importOriginal()),
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
  fieldId,
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
            parameters: {
              table_id: 7,
              current: draft.value,
              ...(fieldId ? { field_id: fieldId } : {}),
            },
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
      5,
      expect.any(String)
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
  const chatUuid = runAction.mock.calls[0][4]
  expect(chatUuid).toEqual(expect.any(String))
  expect(runAction.mock.calls).toEqual([
    [
      'generate_formula',
      'Double it',
      { table_id: 7, current: '1' },
      5,
      chatUuid,
    ],
    [
      'generate_formula',
      'Double it again',
      { table_id: 7, current: '2' },
      5,
      chatUuid,
    ],
  ])
})

test.each([11, 12, undefined])(
  'only reattaches saved history to its original field (%s)',
  async (fieldId) => {
    await mount({ fieldId })
    const store = useNuxtApp().$store
    const id = '22222222-2222-4222-8222-222222222222'
    store.commit('assistant/SET_CHATS', [
      {
        uuid: id,
        title: 'Total',
        editor_context: {
          action: 'generate_formula',
          location: { workspace: { id: 5 } },
          target: { table_id: 7, field_id: 11 },
        },
      },
    ])
    store.commit('assistant/SET_CURRENT_CHAT_ID', id)
    store.commit('assistant/SET_MESSAGES', [
      { role: 'human', content: 'Double it' },
    ])
    try {
      const input = await open()
      const original = fieldId === 11
      expect(useNuxtApp().$kumaEditor.target.value.chatUuid === id).toBe(
        original
      )
      expect(wrapper.text().includes('Double it')).toBe(original)
      expect(input.element.value).toBe(
        original ? '' : 'kumaPrompt.generate_formulaStarter '
      )
    } finally {
      store.commit('assistant/SET_CURRENT_CHAT_ID', null)
      store.commit('assistant/SET_CHATS', [])
      store.commit('assistant/CLEAR_MESSAGES')
    }
  }
)

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

test('puts Copy and a guarded Undo on the filter reply that made the change', async () => {
  await mount({ action: 'update_service_filters' })
  const input = await open()
  const store = useNuxtApp().$store
  const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue('SUCCESS')
  const group = '22222222-2222-4222-8222-222222222222'
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  try {
    runAction.mockResolvedValue({
      changed: true,
      result: {},
      summary: 'Added a filter.',
      actionGroupId: group,
    })
    await input.setValue('Only open tasks')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    const reply = wrapper.get('.chat-message:not(.chat-message--own)')
    const footer = reply.get('.chat-message__footer')
    await footer.get('button[aria-label="action.copy"]').trigger('click')
    expect(writeText).toHaveBeenCalledWith('Added a filter.')
    await footer.get('button:has(.iconoir-undo)').trigger('click')
    expect(dispatch).toHaveBeenCalledWith('undoRedo/undo', {
      showLoadingToast: true,
      expectedActionGroupId: group,
    })
    expect(wrapper.find('.iconoir-undo').exists()).toBe(false)
    runAction.mockResolvedValue({
      changed: false,
      result: {},
      summary: 'Already set.',
      actionGroupId: group,
    })
    await input.setValue('Only open tasks again')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(
      wrapper.findAll('.chat-message:not(.chat-message--own) .iconoir-copy')
    ).toHaveLength(2)
    expect(wrapper.find('.iconoir-undo').exists()).toBe(false)
  } finally {
    vi.unstubAllGlobals()
  }
})

test('selects the saved creation reply before its editor closes', async () => {
  await mount({ action: 'create_table' })
  const input = await open()
  const store = useNuxtApp().$store
  const { chatUuid } = useNuxtApp().$kumaEditor.target.value
  store.commit('assistant/SET_CHATS', [
    { uuid: chatUuid, title: 'Create a table' },
  ])
  const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue(undefined)
  runAction.mockResolvedValue({
    changed: true,
    result: { table_id: 17 },
    summary: 'Created Projects.',
    actionGroupId: 'group',
  })
  try {
    await input.setValue('Create a table for project tracking')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(dispatch).toHaveBeenCalledWith(
      'assistant/selectChat',
      expect.objectContaining({ id: chatUuid })
    )
    expect(wrapper.find('.chat-message__footer .iconoir-undo').exists()).toBe(
      true
    )
  } finally {
    store.commit('assistant/SET_CHATS', [])
  }
})
