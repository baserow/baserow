import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { ref } from 'vue'

import KumaPrompt from '@baserow_enterprise/components/assistant/KumaPrompt'

const mocks = vi.hoisted(() => ({
  available: true,
  runAction: vi.fn(),
  dispatch: null,
}))

// Reactive like the store, so a change re-evaluates what depends on it.
const selectedWorkspace = ref({ id: 1 })

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: () => ({ runAction: mocks.runAction }),
}))

vi.mock('vuex', async (importOriginal) => ({
  ...(await importOriginal()),
  useStore: () => ({
    getters: {
      get 'workspace/getSelected'() {
        return selectedWorkspace.value
      },
    },
    dispatch: mocks.dispatch,
  }),
}))

vi.mock('@baserow_enterprise/utils/assistant', () => ({
  isAssistantAvailable: () => mocks.available,
}))

function mount(props = {}) {
  return mountSuspended(KumaPrompt, {
    global: { stubs: { teleport: true } },
    props: {
      title: 'Create a field',
      placeholder: 'Describe the field',
      action: 'create_field',
      parameters: { table_id: 3 },
      ...props,
    },
  })
}

async function openAndType(wrapper, text) {
  await wrapper.find('.prompt-context__trigger').trigger('click')
  await wrapper.find('textarea').setValue(text)
}

function submitButton(wrapper) {
  return wrapper.find('.prompt-context__input button')
}

describe('KumaPrompt', () => {
  afterEach(() => {
    mocks.runAction.mockReset()
    mocks.available = true
    mocks.dispatch = null
    selectedWorkspace.value = { id: 1 }
  })

  test('renders the link when Kuma is available', async () => {
    const wrapper = await mount()

    expect(wrapper.find('.prompt-context__trigger').text()).toBe(
      'kumaPrompt.askKuma'
    )
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  test('renders nothing when Kuma is not available', async () => {
    mocks.available = false
    const wrapper = await mount()

    expect(wrapper.find('.prompt-context__trigger').exists()).toBe(false)
  })

  test('renders nothing when the host disables it', async () => {
    const wrapper = await mount({ enabled: false })

    expect(wrapper.find('.prompt-context__trigger').exists()).toBe(false)
  })

  test('Shift+Enter keeps editing and Enter sends the request', async () => {
    mocks.runAction.mockResolvedValue({
      changed: false,
      summary: '',
      result: { formula: '1' },
    })
    const wrapper = await mount()
    await openAndType(wrapper, 'One')
    await wrapper
      .get('textarea')
      .trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(mocks.runAction).not.toHaveBeenCalled()
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.emitted('completed')).toEqual([[{ formula: '1' }]])
  })

  test('keeps a no-change explanation inside the popover', async () => {
    mocks.runAction.mockResolvedValue({
      changed: false,
      summary: 'A Due date field already exists.',
    })
    const wrapper = await mount()
    await openAndType(wrapper, '  a due date  ')

    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(mocks.runAction).toHaveBeenCalledWith('create_field', 'a due date', {
      table_id: 3,
    })
    // Active while the request was written and sent.
    expect(wrapper.emitted('active')).toEqual([[true], [false]])
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.get('[role=dialog] .kuma-prompt__result').text()).toContain(
      'A Due date field already exists.'
    )
    await wrapper.get('.kuma-prompt__result .button-icon').trigger('click')
    await openAndType(wrapper, 'Another change')
    expect(wrapper.emitted('active')).toEqual([[true], [false], [true]])
  })

  test('closes the popover when a view filter is saved', async () => {
    mocks.runAction.mockResolvedValue({
      changed: true,
      summary: 'Updated the status filter.',
      result: {},
    })
    const wrapper = await mount({ action: 'edit_view_filters' })
    await openAndType(wrapper, 'Only completed projects')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(
      wrapper.get('.prompt-context__trigger').attributes('aria-expanded')
    ).toBe('false')
    expect(wrapper.find('.kuma-prompt__result').exists()).toBe(false)
    expect(wrapper.emitted('completed')).toEqual([[{}]])
  })

  test('undoes the saved service filters', async () => {
    mocks.dispatch = vi.fn()
    mocks.runAction.mockResolvedValue({
      changed: true,
      summary: 'Added a field.',
    })
    const wrapper = await mount({ action: 'update_service_filters' })
    await openAndType(wrapper, 'a due date')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    await wrapper.find('.kuma-prompt__result button').trigger('click')

    expect(mocks.dispatch).toHaveBeenCalledWith('undoRedo/undo', {
      showLoadingToast: true,
    })
    expect(wrapper.find('.kuma-prompt__result').exists()).toBe(false)
  })

  test('offers no undo when nothing changed', async () => {
    mocks.runAction.mockResolvedValue({
      changed: false,
      summary: 'Nothing to do.',
    })
    const wrapper = await mount()
    await openAndType(wrapper, 'a due date')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.find('.kuma-prompt__result').text()).not.toContain(
      'kumaInlinePrompt.undo'
    )
  })

  test('the host can dismiss the summary', async () => {
    mocks.runAction.mockResolvedValue({
      changed: false,
      summary: 'Added a field.',
    })
    const wrapper = await mount()
    await openAndType(wrapper, 'a due date')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    wrapper.vm.dismiss()
    await flushPromises()

    expect(wrapper.find('.kuma-prompt__result').exists()).toBe(false)
  })

  test('does nothing while the request is empty', async () => {
    const wrapper = await mount()
    await openAndType(wrapper, '   ')

    await submitButton(wrapper).trigger('click')

    expect(mocks.runAction).not.toHaveBeenCalled()
  })

  test('shows why the request is blocked and refuses to send it', async () => {
    const wrapper = await mount({ blockedMessage: 'Save first.' })
    await openAndType(wrapper, 'a due date')

    expect(wrapper.find('.prompt-context__notice').text()).toBe('Save first.')
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })
    expect(mocks.runAction).not.toHaveBeenCalled()
  })

  test('is no longer active when closed', async () => {
    const wrapper = await mount()
    await wrapper.find('.prompt-context__trigger').trigger('click')
    await wrapper.get('textarea').trigger('keydown', { key: 'Escape' })

    expect(wrapper.emitted('active')).toEqual([[true], [false]])
  })

  test('shows the error and keeps the request', async () => {
    const handled = vi.fn()
    const error = new Error('failed')
    error.handler = {
      getMessage: () => ({ message: 'Kuma could not do it.' }),
      handled,
    }
    mocks.runAction.mockRejectedValue(error)
    const wrapper = await mount()
    await openAndType(wrapper, 'a due date')

    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.find('.prompt-context__notice').text()).toBe(
      'Kuma could not do it.'
    )
    expect(wrapper.find('textarea').element.value).toBe('a due date')
    expect(handled).toHaveBeenCalled()
  })

  test('closes when Kuma stops being available', async () => {
    const wrapper = await mount()
    await wrapper.find('.prompt-context__trigger').trigger('click')

    // Kuma's model is switched off: the workspace in the store changes.
    mocks.available = false
    selectedWorkspace.value = { id: 1 }
    await flushPromises()

    expect(wrapper.find('.prompt-context__trigger').exists()).toBe(false)
    expect(wrapper.emitted('active').at(-1)).toEqual([false])
  })
})

test('runs the action with its parameters', async () => {
  const result = { changed: true, summary: 'Updated.', result: { value: 42 } }
  mocks.runAction.mockResolvedValueOnce(result)
  const wrapper = await mount({
    action: 'update_service_filters',
    parameters: { kind: 'builder_data_source', id: 12 },
  })
  await openAndType(wrapper, 'Only done tasks')
  await submitButton(wrapper).trigger('click')
  await flushPromises()
  expect(mocks.runAction).toHaveBeenCalledWith(
    'update_service_filters',
    'Only done tasks',
    { kind: 'builder_data_source', id: 12 }
  )
  expect(wrapper.find('.kuma-prompt__result').text()).toContain('Updated.')
})
