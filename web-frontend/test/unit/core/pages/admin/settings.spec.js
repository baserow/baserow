import { flushPromises } from '@vue/test-utils'

import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import AdminSettings from '@baserow/modules/core/pages/admin/settings'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AdminSettings', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  test.each([
    [200, true, false],
    [500, false, true],
  ])(
    'turning approval off answered %s closes the confirmation: %s',
    async (status, closed, requireApproval) => {
      testApp.store.commit('settings/SET_SETTINGS', {
        user_templates_require_approval: true,
        account_deletion_grace_delay: 30,
      })
      testApp.mock.onGet('/settings/instance-id/').reply(200, {})
      testApp.mock.onPatch('/settings/update/').reply(status, {})
      const wrapper = await testApp.mount(AdminSettings, {
        global: { mocks: { $featureFlagIsEnabled: () => true } },
      })
      await flushPromises()
      const confirmModal = wrapper.findComponent(ConfirmModal)
      const hide = vi.spyOn(confirmModal.vm, 'hide')

      confirmModal.vm.$emit('confirm')
      await flushPromises()

      expect(hide).toHaveBeenCalledTimes(closed ? 1 : 0)
      expect(
        testApp.store.getters['settings/get'].user_templates_require_approval
      ).toBe(requireApproval)
    }
  )
})
