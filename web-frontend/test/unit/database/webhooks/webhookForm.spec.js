import WebhookForm from '@baserow/modules/database/components/webhook/WebhookForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Webhook form Input Tests', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  function mountWebhookForm() {
    return testApp.mount(WebhookForm, {
      propsData: {
        table: { id: 1 },
        database: { id: 2, workspace: { id: 3 } },
        fields: [{ id: 1, name: 'Name', type: 'text' }],
        views: [],
      },
    })
  }

  async function changeURL(wrapper, urlValue) {
    const urlInput = wrapper.find(
      'input[placeholder="webhookForm.inputLabels.url"]'
    )

    urlInput.element.value = urlValue
    await urlInput.trigger('input')
    await urlInput.trigger('blur')
  }

  test('WebhookForm displays an error on missing URL', async () => {
    const wrapper = await mountWebhookForm()
    await changeURL(wrapper, '')

    wrapper.vm.v$.values.url.$touch()

    expect(wrapper.vm.v$.values.url.required.$invalid).toBe(true)
  })

  test('WebhookForm displays an error on too long URL', async () => {
    const wrapper = await mountWebhookForm()
    await changeURL(wrapper, 'http://google.de/' + 'a'.repeat(2001 - 16))
    wrapper.vm.v$.values.url.$touch()
    expect(wrapper.vm.v$.values.url.maxLength.$invalid).toBe(true)
  })

  test('WebhookForm displays an error on invalid URL', async () => {
    const wrapper = await mountWebhookForm()
    await changeURL(wrapper, 'htt://google.de')

    wrapper.vm.v$.values.url.$touch()
    expect(wrapper.vm.v$.values.url.isValidURLWithHttpScheme.$invalid).toBe(
      true
    )
  })
})
