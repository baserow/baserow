import AIProviderItem from '@baserow/modules/core/components/ai/AIProviderItem'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AIProviderItem', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('shows only the provider type and model identifier names', async () => {
    const wrapper = await testApp.mount(AIProviderItem, {
      props: {
        provider: {
          id: 1,
          provider_type: 'openai',
          is_active: true,
          models: [
            {
              id: 2,
              model_identifier: 'gpt-5.6',
              is_enabled: true,
              last_test_status: null,
            },
          ],
        },
        providerType: {
          type: 'openai',
          name: 'OpenAI',
          uses_api_key: true,
        },
      },
    })

    expect(wrapper.find('.ai-provider-card__title').text()).toBe('OpenAI')
    expect(wrapper.text()).toContain('gpt-5.6')
    expect(wrapper.find('.ai-provider-card__models-header').exists()).toBe(
      false
    )
    expect(
      wrapper
        .find('.ai-provider-card__actions')
        .findAll('button')
        .map((button) => button.text())
    ).toEqual([
      'aiProviderAdmin.addModel',
      'aiProviderAdmin.test',
      'action.edit',
      'aiProviderAdmin.disable',
      '',
    ])

    const deleteProviderButton = wrapper
      .find('.ai-provider-card__actions')
      .findAll('button')[4]
    expect(deleteProviderButton.find('.iconoir-bin').exists()).toBe(true)
    expect(deleteProviderButton.attributes('title')).toBe('action.delete')
    expect(deleteProviderButton.attributes('aria-label')).toBe('action.delete')
    expect(deleteProviderButton.classes()).toContain('button--icon-only')

    await wrapper
      .find('.ai-provider-card__actions')
      .findAll('button')[1]
      .trigger('click')
    expect(
      wrapper
        .find('.ai-provider-card__actions')
        .findAll('button')[1]
        .attributes('title')
    ).toBe('aiProviderAdmin.testAllModelsButtonTitle')
    expect(
      wrapper
        .find('.ai-provider-card__actions')
        .findAll('button')[1]
        .find('i')
        .exists()
    ).toBe(false)
    expect(wrapper.emitted('test-all-models')).toEqual([
      [expect.objectContaining({ id: 1 })],
    ])

    const modelTestButton = wrapper
      .find('.ai-provider-model__actions')
      .findAll('button')[0]
    expect(modelTestButton.attributes('title')).toBe(
      'aiProviderAdmin.testModelButtonTitle'
    )
  })

  test('disables the provider test action when there are no models', async () => {
    const wrapper = await testApp.mount(AIProviderItem, {
      props: {
        provider: {
          id: 1,
          provider_type: 'openai',
          is_active: true,
          models: [],
        },
      },
    })

    const testButton = wrapper
      .find('.ai-provider-card__actions')
      .findAll('button')[1]

    expect(testButton.text()).toBe('aiProviderAdmin.test')
    expect(testButton.attributes('disabled')).toBeDefined()
    expect(testButton.attributes('title')).toBe(
      'aiProviderAdmin.testAllModelsButtonTitle'
    )
  })

  test('shows loading feedback on a model while it is being tested', async () => {
    const wrapper = await testApp.mount(AIProviderItem, {
      props: {
        provider: {
          id: 1,
          provider_type: 'openai',
          is_active: true,
          models: [
            {
              id: 2,
              model_identifier: 'gpt-5.6',
              is_enabled: true,
              last_test_status: null,
            },
          ],
        },
        testingModelIds: [2],
      },
    })

    const providerTestButton = wrapper
      .find('.ai-provider-card__actions')
      .findAll('button')[1]
    const modelTestButton = wrapper
      .find('.ai-provider-model__actions')
      .findAll('button')[0]

    expect(providerTestButton.attributes('disabled')).toBeDefined()
    expect(modelTestButton.classes()).toContain('button--loading')
    expect(modelTestButton.attributes('disabled')).toBeDefined()
    expect(
      wrapper
        .find('.ai-provider-card__actions')
        .findAll('button')[2]
        .attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper
        .find('.ai-provider-model__actions')
        .findAll('button')[1]
        .attributes('disabled')
    ).toBeDefined()
  })
})
