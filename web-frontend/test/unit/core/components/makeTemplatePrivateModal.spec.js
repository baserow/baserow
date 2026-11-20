import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import MakeTemplatePrivateModal from '@baserow/modules/core/components/template/MakeTemplatePrivateModal'

const template = {
  id: 3,
  slug: 'sprint-tracker',
  type: 'user',
  name: 'Sprint Tracker',
  state: 'public',
  listed: true,
}

describe('MakeTemplatePrivateModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.authenticate({ id: 1 })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountAndShow = async (props, requireApproval = false) => {
    testApp.store.commit('settings/UPDATE_SETTINGS', {
      user_templates_require_approval: requireApproval,
    })
    const wrapper = await testApp.mount(MakeTemplatePrivateModal, {
      props,
      global: {
        stubs: { Modal: ModalStub },
        mocks: { $t: (key) => key },
      },
    })
    await wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  const button = (wrapper, label) =>
    wrapper.findAll('button').find((button) => button.text() === label)

  test.each([
    [{}, false, 'description', 'publicAgainAnyTime'],
    [{}, true, 'description', 'publicAgainNeedsApproval'],
    [
      { state: 'in_review', listed: false },
      false,
      'reviewDescription',
      'publicAgainNeedsApproval',
    ],
  ])(
    'makes the template private once confirmed, telling what it costs (%o, approval required: %s)',
    async (changes, requireApproval, description, costLine) => {
      const row = { ...template, state: 'private', listed: false }
      testApp.mock.onPatch('/templates/sprint-tracker/').reply(200, row)
      const wrapper = await mountAndShow(
        { template: { ...template, ...changes } },
        requireApproval
      )

      expect(wrapper.find('.user-template-modal__description').text()).toBe(
        `makeTemplatePrivateModal.${description} updateUserTemplateModal.${costLine}`
      )
      expect(testApp.mock.history.patch).toHaveLength(0)

      await button(wrapper, 'makeTemplatePrivateModal.makePrivate').trigger(
        'click'
      )
      await flushPromises()

      expect(
        testApp.mock.history.patch.map(({ data }) => JSON.parse(data))
      ).toStrictEqual([{ visibility: 'private' }])
      expect(wrapper.emitted('made-private')).toStrictEqual([[row]])
      expect(wrapper.findComponent({ name: 'Modal' }).vm.open).toBe(false)
    }
  )
})
