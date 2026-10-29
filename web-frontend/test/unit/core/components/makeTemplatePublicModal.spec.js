import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import { heldBack } from '@baserow/test/helpers/heldBack'
import MakeTemplatePublicModal from '@baserow/modules/core/components/template/MakeTemplatePublicModal'

const template = {
  id: 3,
  revision_id: 5,
  slug: 'sprint-tracker',
  type: 'user',
  name: 'Sprint Tracker',
  state: 'private',
}

describe('MakeTemplatePublicModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.authenticate({ id: 1, first_name: 'Ada', username: 'ada@a.b' })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountAndShow = async () => {
    const wrapper = await testApp.mount(MakeTemplatePublicModal, {
      props: { template },
      global: {
        stubs: { Modal: ModalStub },
        // Shows the parameters, so that the names in the text can be checked.
        mocks: {
          $t: (key, params) =>
            params ? `${key} ${JSON.stringify(params)}` : key,
        },
      },
    })
    await wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  const button = (wrapper, label) =>
    wrapper.findAll('button').find((button) => button.text() === label)

  test('makes the template public with the consent once confirmed', async () => {
    const row = { ...template, state: 'public' }
    testApp.mock.onPatch('/templates/sprint-tracker/').reply(200, row)
    const wrapper = await mountAndShow()

    const description = wrapper.find('.user-template-modal__description')
    expect(description.text()).toContain('“Sprint Tracker”')
    expect(description.find('strong').text()).toBe('Ada')

    await button(wrapper, 'makeTemplatePublicModal.makePublic').trigger('click')
    await flushPromises()

    expect(
      testApp.mock.history.patch.map(({ data }) => JSON.parse(data))
    ).toStrictEqual([
      { listed: true, public_listing_consent: true, revision_id: 5 },
    ])
    expect(wrapper.emitted('made-public')).toStrictEqual([[row]])
    expect(testApp.store.state.toast.items[0]).toMatchObject({
      type: 'success',
      message: 'makeTemplatePublicModal.madePublicDescription',
    })
    expect(wrapper.findComponent({ name: 'Modal' }).vm.open).toBe(false)
  })

  test('sends one request when clicked twice, and stays open for another template', async () => {
    const reply = heldBack()
    testApp.mock.onPatch('/templates/sprint-tracker/').reply(reply.reply)
    const wrapper = await mountAndShow()

    const makePublic = button(wrapper, 'makeTemplatePublicModal.makePublic')
    // Both clicks land before the button is disabled.
    makePublic.trigger('click')
    makePublic.trigger('click')
    await flushPromises()
    await wrapper.setProps({ template: { ...template, id: 4, slug: 'other' } })
    reply.send([200, { ...template, state: 'public' }])
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(1)
    expect(wrapper.emitted('made-public')).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'Modal' }).vm.open).toBe(true)
  })

  test('stays private when the template was updated since it was shown', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock
      .onPatch('/templates/sprint-tracker/')
      .reply(400, { error: 'ERROR_TEMPLATE_UPDATED', detail: '' })
    const wrapper = await mountAndShow()

    await button(wrapper, 'makeTemplatePublicModal.makePublic').trigger('click')
    await flushPromises()

    expect(testApp.store.state.toast.items[0]).toMatchObject({
      type: 'error',
      message: 'makeTemplatePublicModal.updated',
    })
    expect(wrapper.emitted('outdated')).toStrictEqual([[3]])
    expect(wrapper.emitted('made-public')).toBeUndefined()
    expect(wrapper.findComponent({ name: 'Modal' }).vm.open).toBe(false)
  })
})
