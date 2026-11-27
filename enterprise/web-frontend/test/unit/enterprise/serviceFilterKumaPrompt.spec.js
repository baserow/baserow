import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { ref } from 'vue'

import ServiceFilterKumaPrompt from '@baserow_enterprise/components/assistant/ServiceFilterKumaPrompt'

// The prompt itself is tested with `KumaPrompt`. These tests cover what the
// filter form adds: the target, its suggestions, the unsaved changes and freezing.
const mocks = vi.hoisted(() => ({
  runAction: null,
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
  default: () => ({ runAction: mocks.runAction }),
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
      stubs: { teleport: true },
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
  await wrapper.find('.prompt-context__trigger').trigger('click')
  await wrapper.find('textarea').setValue(text)
}

async function send(wrapper, text) {
  await openAndType(wrapper, text)
  await wrapper.find('.prompt-context__input button').trigger('click')
  await flushPromises()
}

function warning(wrapper) {
  return wrapper.find('.prompt-context__notice')
}

describe('ServiceFilterKumaPrompt', () => {
  afterEach(() => {
    mocks.runAction = null
  })

  test('renders nothing without a data source or node to filter', async () => {
    const { wrapper } = await mount({ target: null })

    expect(wrapper.find('.prompt-context__trigger').exists()).toBe(false)
  })

  test('asks Kuma to change the filters of the target', async () => {
    mocks.runAction = vi.fn(async () => ({
      changed: true,
      summary: 'Added a filter on Name.',
    }))
    const { wrapper, filterForm } = await mount()

    await send(wrapper, 'Name is the ID page parameter')

    expect(mocks.runAction).toHaveBeenCalledWith(
      'update_service_filters',
      'Name is the ID page parameter',
      { kind: 'builder_data_source', id: 12, table_id: null }
    )
    // Frozen while the request was written and sent, then released.
    expect(filterForm.setFrozen.mock.calls).toEqual([[true], [false]])
    expect(wrapper.find('.kuma-prompt__result').text()).toContain(
      'Added a filter on Name.'
    )
  })

  test('sends the table picked for a data source without one', async () => {
    mocks.runAction = vi.fn(async () => ({
      changed: true,
      summary: 'Added a filter.',
    }))
    const { wrapper } = await mount({ unsavedTableId: 7 })

    await send(wrapper, 'only done tasks')

    expect(mocks.runAction).toHaveBeenCalledWith(
      'update_service_filters',
      'only done tasks',
      { kind: 'builder_data_source', id: 12, table_id: 7 }
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
    mocks.runAction = vi.fn(async () => ({
      changed: true,
      summary: 'Added a filter.',
    }))
    const unsavedChanges = ref(false)
    const { wrapper } = await mount({ unsavedChanges })
    await send(wrapper, 'only done tasks')
    expect(wrapper.find('.kuma-prompt__result').exists()).toBe(true)

    // The user edits a filter: undo would now revert their edit, not Kuma's.
    unsavedChanges.value = true
    await flushPromises()

    expect(wrapper.find('.kuma-prompt__result').exists()).toBe(false)
  })

  test('releases the filters when unmounted', async () => {
    const { wrapper, filterForm } = await mount()
    await wrapper.find('.prompt-context__trigger').trigger('click')

    wrapper.unmount()

    expect(filterForm.setFrozen).toHaveBeenLastCalledWith(false)
  })
})
