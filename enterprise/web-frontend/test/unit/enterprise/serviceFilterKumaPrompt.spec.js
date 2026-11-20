import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { computed, ref } from 'vue'

import ServiceFilterKumaPrompt from '@baserow_enterprise/components/assistant/ServiceFilterKumaPrompt'

// The prompt itself is tested with `KumaInlinePrompt`. These tests cover what the
// filter form adds: the target, its suggestions, the unsaved changes and freezing.
const mocks = vi.hoisted(() => ({
  updateServiceFilters: null,
}))

vi.mock('vuex', async (importOriginal) => ({
  ...(await importOriginal()),
  useStore: () => ({
    getters: { 'workspace/getSelected': { id: 1 } },
    dispatch: vi.fn(),
  }),
}))

vi.mock('@baserow_enterprise/utils/assistant', () => ({
  isAssistantAvailable: () => true,
}))

vi.mock('@baserow_enterprise/services/assistant', () => ({
  default: () => ({ updateServiceFilters: mocks.updateServiceFilters }),
}))

async function mount({
  target = { kind: 'builder_data_source', id: 12 },
  unsavedChanges = ref(false),
  unsavedTableChange = ref(false),
  unsavedTableId = null,
} = {}) {
  const serviceFilters = {
    hasUnsavedChanges: () => unsavedChanges.value,
    hasUnsavedTableChange: () => unsavedTableChange.value,
    getUnsavedTableId: () => unsavedTableId,
  }
  const filterForm = { setFrozen: vi.fn() }
  const wrapper = await mountSuspended(ServiceFilterKumaPrompt, {
    global: {
      provide: {
        serviceFilterTarget: target,
        serviceFilters,
        serviceFilterForm: filterForm,
      },
    },
  })
  return { wrapper, filterForm }
}

async function openAndType(wrapper, text) {
  await wrapper.find('.kuma-inline-prompt__link').trigger('click')
  await wrapper.find('textarea').setValue(text)
}

async function send(wrapper, text) {
  await openAndType(wrapper, text)
  await wrapper
    .find('.kuma-inline-prompt__actions button:last-child')
    .trigger('click')
  await flushPromises()
}

function warning(wrapper) {
  return wrapper.find('.kuma-inline-prompt__notice--warning')
}

describe('ServiceFilterKumaPrompt', () => {
  afterEach(() => {
    mocks.updateServiceFilters = null
  })

  test('renders nothing without a data source or node to filter', async () => {
    const { wrapper } = await mount({ target: null })

    expect(wrapper.find('.kuma-inline-prompt').exists()).toBe(false)
  })

  test('offers suggestions that fit the data source', async () => {
    const { wrapper } = await mount()
    await wrapper.find('.kuma-inline-prompt__link').trigger('click')

    expect(
      wrapper.findAll('.kuma-inline-prompt__suggestion').map((s) => s.text())
    ).toEqual([
      'serviceFilterKumaPrompt.suggestion_pageParameter',
      'serviceFilterKumaPrompt.suggestion_user',
      'serviceFilterKumaPrompt.suggestion_change',
    ])
  })

  test('accepts the target as a computed', async () => {
    const { wrapper } = await mount({
      target: computed(() => ({ kind: 'automation_node', id: 3 })),
    })
    await wrapper.find('.kuma-inline-prompt__link').trigger('click')

    expect(
      wrapper.findAll('.kuma-inline-prompt__suggestion').map((s) => s.text())
    ).toEqual([
      'serviceFilterKumaPrompt.suggestion_previousNode',
      'serviceFilterKumaPrompt.suggestion_change',
    ])
  })

  test('asks Kuma to change the filters of the target', async () => {
    mocks.updateServiceFilters = vi.fn(async () => ({
      changed: true,
      summary: 'Added a filter on Name.',
    }))
    const { wrapper, filterForm } = await mount()

    await send(wrapper, 'Name is the ID page parameter')

    expect(mocks.updateServiceFilters).toHaveBeenCalledWith(
      'builder_data_source',
      12,
      'Name is the ID page parameter',
      null
    )
    // Frozen while the request was written and sent, then released.
    expect(filterForm.setFrozen.mock.calls).toEqual([[true], [false]])
    expect(wrapper.find('.kuma-inline-prompt__done').text()).toContain(
      'Added a filter on Name.'
    )
  })

  test('sends the table picked for a data source without one', async () => {
    mocks.updateServiceFilters = vi.fn(async () => ({
      changed: true,
      summary: 'Added a filter.',
    }))
    const { wrapper } = await mount({ unsavedTableId: 7 })

    await send(wrapper, 'only done tasks')

    expect(mocks.updateServiceFilters).toHaveBeenCalledWith(
      'builder_data_source',
      12,
      'only done tasks',
      7
    )
  })

  test('asks to save unsaved filter changes first', async () => {
    const { wrapper } = await mount({ unsavedChanges: ref(true) })
    await openAndType(wrapper, 'only done tasks')

    expect(warning(wrapper).text()).toBe(
      'serviceFilterKumaPrompt.unsavedChanges'
    )
  })

  test('asks to save another table first', async () => {
    // Picking another table resets the filters too: the table is what matters.
    const { wrapper } = await mount({
      unsavedChanges: ref(true),
      unsavedTableChange: ref(true),
    })
    await openAndType(wrapper, 'only done tasks')

    expect(warning(wrapper).text()).toBe('serviceFilterKumaPrompt.unsavedTable')
  })

  test('drops the undo once the filters are edited again', async () => {
    mocks.updateServiceFilters = vi.fn(async () => ({
      changed: true,
      summary: 'Added a filter.',
    }))
    const unsavedChanges = ref(false)
    const { wrapper } = await mount({ unsavedChanges })
    await send(wrapper, 'only done tasks')
    expect(wrapper.find('.kuma-inline-prompt__done').exists()).toBe(true)

    // The user edits a filter: undo would now revert their edit, not Kuma's.
    unsavedChanges.value = true
    await flushPromises()

    expect(wrapper.find('.kuma-inline-prompt__done').exists()).toBe(false)
  })

  test('releases the filters when unmounted', async () => {
    const { wrapper, filterForm } = await mount()
    await wrapper.find('.kuma-inline-prompt__link').trigger('click')

    wrapper.unmount()

    expect(filterForm.setFrozen).toHaveBeenLastCalledWith(false)
  })
})
