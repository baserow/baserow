import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarWorkspacePickerRow from '@baserow/modules/core/components/sidebar/SidebarWorkspacePickerRow.vue'

describe('SidebarWorkspacePickerRow', () => {
  let testApp
  let respond

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Design',
    })
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    // The response is only sent when the test calls `respond`.
    testApp.mock.onPatch('/workspaces/1/').reply(
      () =>
        new Promise((resolve) => {
          respond = resolve
        })
    )
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function renameTo(name) {
    const wrapper = await testApp.mount(SidebarWorkspacePickerRow, {
      props: { workspace: testApp.store.getters['workspace/get'](1) },
      global: {
        mocks: { $hasPermission: () => true },
        stubs: { Teleport: false },
      },
    })
    await wrapper.get('.sidebar-workspace-picker__actions').trigger('click')
    await flushPromises()
    await testApp.body
      .findAll('button')
      .find((button) => button.text() === 'workspaceContext.renameWorkspace')
      .trigger('click')
    await flushPromises()

    const editable = wrapper.get('[contenteditable="true"]')
    editable.element.textContent = name
    await editable.trigger('input')
    await editable.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    return wrapper
  }

  test('shows the new name while the rename request is pending', async () => {
    const wrapper = await renameTo('Product')
    const option = wrapper.get('[data-workspace-option]')
    const name = option.get('.sidebar-workspace-picker__name')

    expect(option.isVisible()).toBe(true)
    expect(name.text()).toBe('Product')

    respond([200, { id: 1, name: 'Product' }])
    await flushPromises()
    expect(name.text()).toBe('Product')
  })

  test('shows the old name again when the rename fails', async () => {
    testApp.dontFailOnErrorResponses()
    const wrapper = await renameTo('Product')
    const option = wrapper.get('[data-workspace-option]')
    const name = option.get('.sidebar-workspace-picker__name')
    expect(name.text()).toBe('Product')

    respond([400, { error: 'ERROR_REQUEST_BODY_VALIDATION', detail: {} }])
    await flushPromises()
    expect(name.text()).toBe('Design')
  })
})
