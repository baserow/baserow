import flushPromises from 'flush-promises'

import SMTPForm from '@baserow/modules/integrations/core/components/integrations/SMTPForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('SMTP integration form', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(props = {}) {
    return await testApp.mount(SMTPForm, {
      props: {
        application: { id: 1 },
        ...props,
      },
    })
  }

  test('renders the default SMTP values', async () => {
    const wrapper = await mountComponent()
    const inputs = wrapper.findAll('.form-input__input')

    expect(inputs).toHaveLength(4)
    expect(inputs.at(0).element.value).toBe('')
    expect(inputs.at(1).element.value).toBe('587')
    expect(inputs.at(2).element.value).toBe('')
    expect(inputs.at(3).element.value).toBe('')
    expect(wrapper.find('.checkbox').classes()).toContain('checkbox--checked')
  })

  test('emits updated values with the parsed SMTP port', async () => {
    const wrapper = await mountComponent()
    const inputs = wrapper.findAll('.form-input__input')

    await inputs.at(0).setValue('smtp.example.com')
    await inputs.at(1).setValue('2525')
    await wrapper.find('.checkbox').trigger('click')
    await inputs.at(2).setValue('mailer')
    await inputs.at(3).setValue('secret')
    await flushPromises()

    const emittedValues = wrapper.emitted('values-changed')
    const lastEmission = emittedValues.at(-1)[0]

    expect(lastEmission).toEqual({
      host: 'smtp.example.com',
      port: 2525,
      use_tls: false,
      username: 'mailer',
      password: 'secret',
    })
  })

  test('shows validation messages when the host is empty and the port is invalid', async () => {
    const wrapper = await mountComponent()
    const inputs = wrapper.findAll('.form-input__input')

    await inputs.at(0).trigger('blur')
    await inputs.at(1).setValue('0')
    await inputs.at(1).trigger('blur')
    await flushPromises()

    expect(wrapper.findAll('.control__messages--error')).toHaveLength(2)
  })
})
