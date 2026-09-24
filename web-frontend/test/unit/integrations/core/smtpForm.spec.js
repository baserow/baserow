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
    expect(
      wrapper.findComponent({ name: 'Dropdown' }).props('modelValue')
    ).toBe('starttls')
  })

  test('emits updated values with the parsed SMTP port', async () => {
    const wrapper = await mountComponent()
    const inputs = wrapper.findAll('.form-input__input')

    await inputs.at(0).setValue('smtp.example.com')
    await inputs.at(1).setValue('2525')
    wrapper
      .findComponent({ name: 'Dropdown' })
      .vm.$emit('update:modelValue', 'none')
    await inputs.at(2).setValue('mailer')
    await inputs.at(3).setValue('secret')
    await flushPromises()

    const emittedValues = wrapper.emitted('values-changed')
    const lastEmission = emittedValues.at(-1)[0]

    expect(lastEmission).toEqual({
      host: 'smtp.example.com',
      port: 2525,
      use_tls: false,
      use_ssl: false,
      username: 'mailer',
      password: 'secret',
    })
  })

  test('selecting SSL/TLS turns STARTTLS off', async () => {
    const wrapper = await mountComponent()

    wrapper
      .findComponent({ name: 'Dropdown' })
      .vm.$emit('update:modelValue', 'ssl')
    await flushPromises()

    const lastEmission = wrapper.emitted('values-changed').at(-1)[0]
    expect(lastEmission.use_tls).toBe(false)
    expect(lastEmission.use_ssl).toBe(true)
  })

  test('switches a conventional port along with the security mode', async () => {
    const wrapper = await mountComponent()
    const dropdown = wrapper.findComponent({ name: 'Dropdown' })

    dropdown.vm.$emit('update:modelValue', 'ssl')
    await flushPromises()
    expect(wrapper.vm.getFormValues().port).toBe(465)

    dropdown.vm.$emit('update:modelValue', 'starttls')
    await flushPromises()
    expect(wrapper.vm.getFormValues().port).toBe(587)

    dropdown.vm.$emit('update:modelValue', 'none')
    await flushPromises()
    expect(wrapper.vm.getFormValues().port).toBe(587)
  })

  test('keeps a custom port when the security mode changes', async () => {
    const wrapper = await mountComponent()

    await wrapper.findAll('.form-input__input').at(1).setValue('2525')
    wrapper
      .findComponent({ name: 'Dropdown' })
      .vm.$emit('update:modelValue', 'ssl')
    await flushPromises()

    expect(wrapper.vm.getFormValues().port).toBe(2525)
  })

  test('shows SSL/TLS for an integration using implicit SSL', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        host: 'smtp.strato.de',
        port: 465,
        use_tls: false,
        use_ssl: true,
        username: 'mailer',
        has_password: true,
      },
    })

    expect(
      wrapper.findComponent({ name: 'Dropdown' }).props('modelValue')
    ).toBe('ssl')
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

  test('omits an untouched password from the submitted values', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        host: 'smtp.example.com',
        port: 587,
        use_tls: true,
        username: 'mailer',
        has_password: true,
      },
    })

    expect('password' in wrapper.vm.getFormValues()).toBe(false)
  })

  test('includes a password the user typed', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        host: 'smtp.example.com',
        port: 587,
        use_tls: true,
        username: 'mailer',
        has_password: true,
      },
    })
    await wrapper.find('input[type="password"]').setValue('newsecret')
    await flushPromises()

    expect(wrapper.vm.getFormValues().password).toBe('newsecret')
  })

  test('sends an empty string when the user clears a typed password', async () => {
    const wrapper = await mountComponent({
      defaultValues: {
        host: 'smtp.example.com',
        port: 587,
        use_tls: true,
        username: 'mailer',
        has_password: true,
      },
    })
    const password = wrapper.find('input[type="password"]')

    await password.setValue('typed')
    await password.setValue('')
    await flushPromises()

    expect(wrapper.vm.getFormValues().password).toBe('')
  })
})
