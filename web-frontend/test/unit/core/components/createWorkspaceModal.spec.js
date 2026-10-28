import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'

describe('CreateWorkspaceModal', () => {
  let testApp = null
  let push = null

  beforeEach(() => {
    testApp = new TestApp()
    push = vi.spyOn(testApp.nuxtApp.$router, 'push').mockResolvedValue()
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    testApp.mock
      .onPost('/workspaces/')
      .reply(200, { id: 3, name: 'New', order: 1, users: [] })
    testApp.mock.onGet('/workspaces/3/permissions/').reply(200, [])
  })

  afterEach(async () => {
    push.mockRestore()
    await testApp.afterEach()
  })

  test('stays on the page and reports the workspace once', async () => {
    const wrapper = await testApp.mount(CreateWorkspaceModal, {
      props: { navigate: false },
    })
    wrapper.vm.show()
    await wrapper.vm.submitted({ name: 'New' })
    await flushPromises()

    expect(push).not.toHaveBeenCalled()
    expect(wrapper.emitted('created')).toHaveLength(1)
    expect(wrapper.emitted('created')[0][0].id).toBe(3)
    expect(testApp.store.getters['workspace/getSelected'].id).toBe(3)
    expect(wrapper.vm.$refs.modal.isOpen()).toBe(false)
  })

  test('goes to the new workspace by default', async () => {
    const wrapper = await testApp.mount(CreateWorkspaceModal)
    wrapper.vm.show()
    // Resolves after the navigation, which this test doesn't finish.
    wrapper.vm.submitted({ name: 'New' })
    await flushPromises()

    expect(push).toHaveBeenCalledWith({
      name: 'workspace',
      params: { workspaceId: 3 },
    })
    expect(wrapper.emitted('created')[0][0].id).toBe(3)
  })
})
