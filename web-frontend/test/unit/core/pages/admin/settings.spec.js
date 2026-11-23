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

  const mountSettings = async (key, value, flag = true) => {
    testApp.store.commit('settings/SET_SETTINGS', {
      allow_user_templates: true,
      user_templates_require_approval: true,
      account_deletion_grace_delay: 30,
      [key]: value,
    })
    testApp.mock.onGet('/settings/instance-id/').reply(200, {})
    const wrapper = await testApp.mount(AdminSettings, {
      global: { mocks: { $featureFlagIsEnabled: () => flag } },
    })
    await flushPromises()
    return wrapper
  }

  const item = (wrapper, name) =>
    wrapper
      .findAll('.admin-settings__item')
      .find((el) => el.find('.admin-settings__name').text() === name)

  describe.each([
    ['allow_user_templates', 'settings.settingAllowUserTemplatesName', 0],
    [
      'user_templates_require_approval',
      'settings.settingUserTemplatesRequireApprovalName',
      1,
    ],
  ])('%s', (key, name, modalIndex) => {
    test('turns on without asking and asks before turning off', async () => {
      testApp.mock.onPatch('/settings/update/').reply(200, {})
      const wrapper = await mountSettings(key, false)
      const confirmModal = wrapper.findAllComponents(ConfirmModal)[modalIndex]
      const show = vi.spyOn(confirmModal.vm, 'show')
      const toggle = item(wrapper, name).find('.switch')

      await toggle.trigger('click')
      await flushPromises()

      expect(show).not.toHaveBeenCalled()
      expect(JSON.parse(testApp.mock.history.patch[0].data)).toStrictEqual({
        [key]: true,
      })

      await toggle.trigger('click')

      expect(show).toHaveBeenCalledTimes(1)
      expect(testApp.mock.history.patch).toHaveLength(1)
      expect(testApp.store.getters['settings/get'][key]).toBe(true)
    })

    test.each([
      [200, true, false],
      [500, false, true],
    ])(
      'turning it off answered %s closes the confirmation: %s',
      async (status, closed, value) => {
        testApp.mock.onPatch('/settings/update/').reply(status, {})
        const wrapper = await mountSettings(key, true)
        const confirmModal = wrapper.findAllComponents(ConfirmModal)[modalIndex]
        const hide = vi.spyOn(confirmModal.vm, 'hide')

        confirmModal.vm.$emit('confirm')
        await flushPromises()

        expect(hide).toHaveBeenCalledTimes(closed ? 1 : 0)
        expect(JSON.parse(testApp.mock.history.patch[0].data)).toStrictEqual({
          [key]: false,
        })
        expect(testApp.store.getters['settings/get'][key]).toBe(value)
      }
    )
  })

  test('hides the user template toggles without their feature flag', async () => {
    const wrapper = await mountSettings('allow_user_templates', true, false)

    expect(
      item(wrapper, 'settings.settingAllowUserTemplatesName')
    ).toBeUndefined()
    expect(wrapper.findAllComponents(ConfirmModal)).toHaveLength(0)
  })
})
