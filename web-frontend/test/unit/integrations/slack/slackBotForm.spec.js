import flushPromises from 'flush-promises'

import SlackBotForm from '@baserow/modules/integrations/slack/components/integrations/SlackBotForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Slack bot integration form', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(props = {}) {
    return await testApp.mount(SlackBotForm, {
      props: {
        application: { id: 1 },
        ...props,
      },
    })
  }

  test('omits an untouched token from the submitted values', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })

    expect('token' in wrapper.vm.getFormValues()).toBe(false)
  })

  test('includes a token the user typed', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })

    await wrapper.find('.form-input__input').setValue('xoxb-new')
    await flushPromises()

    expect(wrapper.vm.getFormValues().token).toBe('xoxb-new')
  })

  test('omits a token the user typed and then cleared', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })
    const input = wrapper.find('.form-input__input')

    await input.setValue('xoxb-new')
    await input.setValue('')
    await flushPromises()

    expect('token' in wrapper.vm.getFormValues()).toBe(false)
  })

  test('does not require a token when one is already saved', async () => {
    const wrapper = await mountComponent({
      defaultValues: { has_token: true },
    })

    wrapper.vm.touch()
    await flushPromises()

    expect(wrapper.vm.isFormValid()).toBe(true)
  })

  test('requires a token when none is saved', async () => {
    const wrapper = await mountComponent({ defaultValues: {} })

    wrapper.vm.touch()
    await flushPromises()

    expect(wrapper.vm.isFormValid()).toBe(false)
  })
})
