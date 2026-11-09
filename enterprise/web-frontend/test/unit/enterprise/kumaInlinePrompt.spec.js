import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { ref } from 'vue'

import KumaInlinePrompt from '@baserow_enterprise/components/assistant/KumaInlinePrompt'

const mocks = vi.hoisted(() => ({
  available: true,
  dispatch: null,
}))

// Reactive like the store, so a change re-evaluates what depends on it.
const selectedWorkspace = ref({ id: 1 })

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
  return mountSuspended(KumaInlinePrompt, {
    props: {
      title: 'Create a field',
      placeholder: 'Describe the field',
      submitLabel: 'Create field',
      workingLabel: 'Writing your field…',
      request: vi.fn(),
      ...props,
    },
  })
}

async function openAndType(wrapper, text) {
  await wrapper.find('.kuma-inline-prompt__link').trigger('click')
  await wrapper.find('textarea').setValue(text)
}

function submitButton(wrapper) {
  return wrapper.find('.kuma-inline-prompt__actions button:last-child')
}

describe('KumaInlinePrompt', () => {
  afterEach(() => {
    mocks.available = true
    mocks.dispatch = null
    selectedWorkspace.value = { id: 1 }
  })

  test('renders the link when Kuma is available', async () => {
    const wrapper = await mount({ linkLabel: 'Ask Kuma', withDivider: true })

    expect(wrapper.find('.kuma-inline-prompt__link').text()).toBe('Ask Kuma')
    expect(wrapper.find('.kuma-inline-prompt__divider').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  test('renders nothing when Kuma is not available', async () => {
    mocks.available = false
    const wrapper = await mount()

    expect(wrapper.find('.kuma-inline-prompt').exists()).toBe(false)
  })

  test('renders nothing when the host disables it', async () => {
    const wrapper = await mount({ enabled: false })

    expect(wrapper.find('.kuma-inline-prompt').exists()).toBe(false)
  })

  test('fills the request with a suggestion', async () => {
    const wrapper = await mount({
      suggestions: [{ key: 'a', label: 'Use a date', prompt: 'A date field' }],
    })
    await wrapper.find('.kuma-inline-prompt__link').trigger('click')

    const suggestions = wrapper.findAll('.kuma-inline-prompt__suggestion')
    expect(suggestions.map((s) => s.text())).toEqual(['Use a date'])
    await suggestions[0].trigger('click')
    expect(wrapper.find('textarea').element.value).toBe('A date field')
  })

  test('sends the request and shows the summary', async () => {
    const request = vi.fn(async () => ({
      changed: true,
      summary: 'Added a Due date field.',
    }))
    const wrapper = await mount({ request })
    await openAndType(wrapper, '  a due date  ')

    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(request).toHaveBeenCalledWith('a due date')
    // Active while the request was written and sent.
    expect(wrapper.emitted('active')).toEqual([[true], [false]])
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.find('.kuma-inline-prompt__done').text()).toContain(
      'Added a Due date field.'
    )
  })

  test('undoes the change', async () => {
    mocks.dispatch = vi.fn()
    const wrapper = await mount({
      request: async () => ({ changed: true, summary: 'Added a field.' }),
    })
    await openAndType(wrapper, 'a due date')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    await wrapper
      .find('.kuma-inline-prompt__done-actions button')
      .trigger('click')

    expect(mocks.dispatch).toHaveBeenCalledWith('undoRedo/undo', {
      showLoadingToast: true,
    })
    expect(wrapper.find('.kuma-inline-prompt__done').exists()).toBe(false)
  })

  test('offers no undo when nothing changed', async () => {
    const wrapper = await mount({
      request: async () => ({ changed: false, summary: 'Nothing to do.' }),
    })
    await openAndType(wrapper, 'a due date')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.find('.kuma-inline-prompt__done').text()).not.toContain(
      'kumaInlinePrompt.undo'
    )
  })

  test('the host can dismiss the summary', async () => {
    const wrapper = await mount({
      request: async () => ({ changed: true, summary: 'Added a field.' }),
    })
    await openAndType(wrapper, 'a due date')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    wrapper.vm.dismiss()
    await flushPromises()

    expect(wrapper.find('.kuma-inline-prompt__done').exists()).toBe(false)
  })

  test('does nothing while the request is empty', async () => {
    const request = vi.fn()
    const wrapper = await mount({ request })
    await openAndType(wrapper, '   ')

    await submitButton(wrapper).trigger('click')

    expect(request).not.toHaveBeenCalled()
  })

  test('shows why the request is blocked and refuses to send it', async () => {
    const request = vi.fn()
    const wrapper = await mount({ request, blockedMessage: 'Save first.' })
    await openAndType(wrapper, 'a due date')

    expect(wrapper.find('.kuma-inline-prompt__notice--warning').text()).toBe(
      'Save first.'
    )
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })
    expect(request).not.toHaveBeenCalled()
  })

  test('is no longer active when closed', async () => {
    const wrapper = await mount()
    await wrapper.find('.kuma-inline-prompt__link').trigger('click')
    await wrapper.find('.kuma-inline-prompt__header button').trigger('click')

    expect(wrapper.emitted('active')).toEqual([[true], [false]])
  })

  test('shows the error and keeps the request', async () => {
    const handled = vi.fn()
    const wrapper = await mount({
      request: async () => {
        const error = new Error('failed')
        error.handler = {
          getMessage: () => ({ message: 'Kuma could not do it.' }),
          handled,
        }
        throw error
      },
    })
    await openAndType(wrapper, 'a due date')

    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.find('.kuma-inline-prompt__notice--error').text()).toBe(
      'Kuma could not do it.'
    )
    expect(wrapper.find('textarea').element.value).toBe('a due date')
    expect(submitButton(wrapper).text()).toBe('kumaInlinePrompt.tryAgain')
    expect(handled).toHaveBeenCalled()
  })

  test('closes when Kuma stops being available', async () => {
    const wrapper = await mount()
    await wrapper.find('.kuma-inline-prompt__link').trigger('click')

    // Kuma's model is switched off: the workspace in the store changes.
    mocks.available = false
    selectedWorkspace.value = { id: 1 }
    await flushPromises()

    expect(wrapper.find('.kuma-inline-prompt').exists()).toBe(false)
    expect(wrapper.emitted('active').at(-1)).toEqual([false])
  })
})
