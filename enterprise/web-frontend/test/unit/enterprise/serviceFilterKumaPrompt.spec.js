import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { ref } from 'vue'
import { useNuxtApp } from '#app'

import ServiceFilterKumaPrompt from '@baserow_enterprise/components/assistant/ServiceFilterKumaPrompt'

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

let mounted
afterEach(() => mounted?.unmount())

async function mount({
  target = { kind: 'builder_data_source', id: 12 },
  unsavedChanges = ref(false),
  unsavedTableChange = ref(false),
  selectedTableId = ref(null),
} = {}) {
  const serviceFilters = {
    hasUnsavedChanges: () => unsavedChanges.value,
    hasUnsavedTableChange: () => unsavedTableChange.value,
    getSelectedTableId: () => selectedTableId.value,
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
  mounted = wrapper
  return { wrapper, filterForm }
}

describe('service filter sidebar context', () => {
  test('requires a saved service target', async () => {
    const { wrapper } = await mount({ target: null })
    expect(wrapper.find('button').exists()).toBe(false)
  })

  test('binds the service and selected table and releases the form when closed', async () => {
    const { wrapper, filterForm } = await mount({ selectedTableId: ref(7) })
    await wrapper.get('button').trigger('click')
    const { target } = useNuxtApp().$kumaEditor
    expect(target.value.action).toBe('update_service_filters')
    expect(target.value.parameters).toEqual({
      kind: 'builder_data_source',
      id: 12,
      table_id: 7,
    })
    target.value.busy(true)
    expect(filterForm.setFrozen).toHaveBeenLastCalledWith(true)
    wrapper.unmount()
    mounted = null
    expect(filterForm.setFrozen).toHaveBeenLastCalledWith(false)
    expect(target.value).toBeNull()
  })

  test('detaches the conversation when the selected table changes', async () => {
    const selectedTableId = ref(7)
    const { wrapper } = await mount({ selectedTableId })
    await wrapper.get('button').trigger('click')
    const { target } = useNuxtApp().$kumaEditor
    const chat = target.value.chatUuid
    selectedTableId.value = 8
    await flushPromises()
    expect(target.value).toBeNull()
    await wrapper.get('button').trigger('click')
    expect(target.value.chatUuid).not.toBe(chat)
    expect(target.value.parameters.table_id).toBe(8)
  })

  test('exposes unsaved changes and invalidates undo after manual edits', async () => {
    const unsavedChanges = ref(false)
    const unsavedTableChange = ref(false)
    const { wrapper } = await mount({ unsavedChanges, unsavedTableChange })
    await wrapper.get('button').trigger('click')
    const { target } = useNuxtApp().$kumaEditor
    target.value.undoGroup.value = 'group-id'
    unsavedChanges.value = true
    await flushPromises()
    expect(target.value.blockedMessage).toBe(
      'serviceFilterKumaPrompt.unsavedChanges'
    )
    expect(target.value.undoGroup.value).toBeNull()
    unsavedTableChange.value = true
    await flushPromises()
    expect(target.value.blockedMessage).toBe(
      'serviceFilterKumaPrompt.unsavedTable'
    )
  })
})
