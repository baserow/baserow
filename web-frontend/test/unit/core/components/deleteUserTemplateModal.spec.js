import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import { heldBack } from '@baserow/test/helpers/heldBack'
import DeleteUserTemplateModal from '@baserow/modules/core/components/template/DeleteUserTemplateModal'

const userTemplate = (values = {}) => ({
  id: 3,
  slug: 'sprint-tracker',
  type: 'user',
  name: 'Sprint Tracker',
  state: 'public',
  ...values,
})

describe('DeleteUserTemplateModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountAndShow = async (template = userTemplate()) => {
    const wrapper = await testApp.mount(DeleteUserTemplateModal, {
      props: { template },
      global: {
        stubs: { Modal: ModalStub },
        // Shows the parameters, so that the name in the title can be checked.
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

  const deleteButton = (wrapper) =>
    button(wrapper, 'deleteUserTemplateModal.delete')

  const isModalOpen = (wrapper) =>
    wrapper.findComponent({ name: 'Modal' }).vm.open

  // Replies to the deletion only when `send` is called.
  const holdDeletion = (slug = 'sprint-tracker') => {
    const deletion = heldBack()
    testApp.mock.onDelete(`/templates/${slug}/`).reply(deletion.reply)
    return deletion
  }

  test('asks to confirm with the name of the template', async () => {
    const wrapper = await mountAndShow()

    expect(wrapper.find('.user-template-modal__title').text()).toBe(
      'deleteUserTemplateModal.title {"name":"Sprint Tracker"}'
    )
    expect(wrapper.find('.user-template-modal__description').text()).toBe(
      'deleteUserTemplateModal.description'
    )
    expect(deleteButton(wrapper).classes()).toContain('button--danger')
    expect(button(wrapper, 'action.cancel').exists()).toBe(true)
  })

  test('deletes the template and closes', async () => {
    testApp.mock.onDelete('/templates/sprint-tracker/').reply(204)
    const wrapper = await mountAndShow()

    await deleteButton(wrapper).trigger('click')
    await flushPromises()

    expect(testApp.mock.history.delete.map((r) => r.url)).toStrictEqual([
      '/templates/sprint-tracker/',
    ])
    expect(wrapper.emitted('deleted')).toStrictEqual([
      [3, false, expect.any(Number)],
    ])
    expect(isModalOpen(wrapper)).toBe(false)
  })

  test('shows the deletion running and sends it once', async () => {
    const held = holdDeletion()
    const wrapper = await mountAndShow()

    await deleteButton(wrapper).trigger('click')
    await flushPromises()

    expect(deleteButton(wrapper).attributes('disabled')).toBeDefined()
    expect(deleteButton(wrapper).classes()).toContain('button--loading')

    await deleteButton(wrapper).trigger('click')
    // Even when the click reaches the handler.
    wrapper.vm.$.setupState.confirm()
    await flushPromises()

    expect(testApp.mock.history.delete).toHaveLength(1)

    held.send([204])
    await flushPromises()

    expect(wrapper.emitted('deleted')).toStrictEqual([
      [3, false, expect.any(Number)],
    ])
  })

  test('keeps the modal open and shows the error when it fails', async () => {
    testApp.mock.onDelete('/templates/sprint-tracker/').reply(500)
    const wrapper = await mountAndShow()

    await deleteButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.emitted('deleted')).toBeUndefined()
    expect(isModalOpen(wrapper)).toBe(true)
    expect(testApp.store.state.toast.items).toHaveLength(1)
    expect(testApp.store.state.toast.items[0].type).toBe('error')
    expect(deleteButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  test('treats a template that is already deleted as deleted and says so', async () => {
    testApp.mock.onDelete('/templates/sprint-tracker/').reply(404, {
      error: 'ERROR_TEMPLATE_DOES_NOT_EXIST',
      detail: 'The requested template does not exist.',
    })
    const wrapper = await mountAndShow()

    await deleteButton(wrapper).trigger('click')
    await flushPromises()

    // Says that it was already deleted.
    expect(wrapper.emitted('deleted')).toStrictEqual([
      [3, true, expect.any(Number)],
    ])
    expect(isModalOpen(wrapper)).toBe(false)
    expect(testApp.store.state.toast.items).toHaveLength(0)
  })

  test('closes without deleting on cancel', async () => {
    const wrapper = await mountAndShow()

    await button(wrapper, 'action.cancel').trigger('click')
    await flushPromises()

    expect(isModalOpen(wrapper)).toBe(false)
    expect(wrapper.emitted('hidden')).toHaveLength(1)
    expect(testApp.mock.history.delete).toHaveLength(0)
    expect(wrapper.emitted('deleted')).toBeUndefined()
  })

  test('reports a deletion that ends after it was opened for another template', async () => {
    const held = holdDeletion()
    const wrapper = await mountAndShow()

    await deleteButton(wrapper).trigger('click')
    await wrapper.vm.hide()
    await wrapper.setProps({
      template: userTemplate({ id: 4, slug: 'other', name: 'Other' }),
    })
    await wrapper.vm.show()
    await flushPromises()

    // The running deletion is of the other template.
    expect(deleteButton(wrapper).attributes('disabled')).toBeUndefined()

    held.send([204])
    await flushPromises()

    expect(wrapper.emitted('deleted')).toStrictEqual([
      [3, false, expect.any(Number)],
    ])
    // Still asking about the other template.
    expect(isModalOpen(wrapper)).toBe(true)
  })
})
