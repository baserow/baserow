import flushPromises from 'flush-promises'

import AIForm from '@baserow/modules/integrations/ai/components/integrations/AIForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AI integration form', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(props = {}) {
    return await testApp.mount(AIForm, {
      props: {
        application: { id: 1, workspace: { id: 1 } },
        ...props,
      },
    })
  }

  async function overrideOpenAI(wrapper) {
    const card = wrapper
      .findAll('.expandable')
      .find((expandable) =>
        expandable.text().includes('generativeAIModelType.openai')
      )
    await card.find('a').trigger('click')
    await card.find('.checkbox').trigger('click')
    await flushPromises()

    const inputs = card.findAll('.form-input__input')
    return { apiKey: inputs.at(0), models: inputs.at(3) }
  }

  test('submits an OpenAI override without a base URL', async () => {
    const wrapper = await mountComponent()
    const { apiKey, models } = await overrideOpenAI(wrapper)

    await apiKey.setValue('sk-integration')
    await models.setValue('gpt-5.6')
    wrapper.vm.submit()
    await flushPromises()

    expect(wrapper.findAll('.control__messages--error')).toHaveLength(0)
    expect(wrapper.emitted('submitted')).toEqual([
      [
        {
          ai_settings: {
            openai: {
              api_key: 'sk-integration',
              organization: '',
              base_url: '',
              models: ['gpt-5.6'],
            },
          },
        },
      ],
    ])
  })

  async function mountWithSavedKey() {
    const wrapper = await mountComponent({
      defaultValues: {
        ai_settings: {
          openai: {
            has_api_key: true,
            organization: '',
            base_url: '',
            models: ['gpt-5.6'],
          },
        },
      },
    })
    const card = wrapper
      .findAll('.expandable')
      .find((expandable) =>
        expandable.text().includes('generativeAIModelType.openai')
      )
    await card.find('a').trigger('click')
    await flushPromises()

    const inputs = card.findAll('.form-input__input')
    return { wrapper, apiKey: inputs.at(0), baseUrl: inputs.at(2) }
  }

  test('requires the API key again when a connection setting changes', async () => {
    const { wrapper, baseUrl } = await mountWithSavedKey()

    await baseUrl.setValue('https://other.example')
    wrapper.vm.submit()
    await flushPromises()

    expect(wrapper.findAll('.control__messages--error')).toHaveLength(1)
    expect(wrapper.emitted('submitted')).toBeUndefined()
  })

  test('does not keep the saved API key once the field is cleared', async () => {
    const { wrapper, apiKey } = await mountWithSavedKey()

    await apiKey.setValue('sk-typed')
    await apiKey.setValue('')
    wrapper.vm.submit()
    await flushPromises()

    expect(wrapper.findAll('.control__messages--error')).toHaveLength(1)
    expect(wrapper.emitted('submitted')).toBeUndefined()
  })

  test('keeps the saved API key when it is not retyped', async () => {
    const { wrapper, apiKey } = await mountWithSavedKey()

    expect(apiKey.attributes('type')).toBe('password')
    expect(apiKey.element.value).toBe('')

    wrapper.vm.submit()
    await flushPromises()

    expect(wrapper.findAll('.control__messages--error')).toHaveLength(0)
    expect(wrapper.emitted('submitted')).toEqual([
      [
        {
          ai_settings: {
            openai: {
              organization: '',
              base_url: '',
              models: ['gpt-5.6'],
            },
          },
        },
      ],
    ])
  })
})
