import AIProviderItem from '@baserow/modules/core/components/ai/AIProviderItem'
import { TestApp } from '@baserow/test/helpers/testApp'

function expectIconAction(button, icon, title) {
  expect(button.find(`.${icon}`).exists()).toBe(true)
  expect(button.attributes('title')).toBe(title)
  expect(button.attributes('aria-label')).toBe(title)
  expect(button.classes()).toContain('button--icon-only')
}

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
      '',
      '',
      '',
    ])

    const providerEditButton = wrapper
      .find('.ai-provider-card__actions')
      .findAll('button')[2]
    expectIconAction(providerEditButton, 'iconoir-edit', 'action.edit')

    const providerDisableButton = wrapper
      .find('.ai-provider-card__actions')
      .findAll('button')[3]
    expectIconAction(
      providerDisableButton,
      'iconoir-eye-off',
      'aiProviderAdmin.disable'
    )

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

    const modelActionButtons = wrapper
      .find('.ai-provider-model__actions')
      .findAll('button')
    const modelEditButton = modelActionButtons[1]
    expectIconAction(modelEditButton, 'iconoir-edit', 'action.edit')

    const modelDisableButton = modelActionButtons[2]
    expectIconAction(
      modelDisableButton,
      'iconoir-eye-off',
      'aiProviderAdmin.disable'
    )
  })

  test('uses enable actions for an inactive provider and disabled model', async () => {
    const wrapper = await testApp.mount(AIProviderItem, {
      props: {
        provider: {
          id: 1,
          provider_type: 'openai',
          is_active: false,
          models: [
            {
              id: 2,
              model_identifier: 'gpt-5.6',
              is_enabled: false,
              last_test_status: null,
            },
          ],
        },
      },
    })

    expect(wrapper.findAll('.iconoir-eye-empty')).toHaveLength(2)

    const providerEnableButton = wrapper
      .find('.ai-provider-card__actions')
      .findAll('button')[3]
    expectIconAction(
      providerEnableButton,
      'iconoir-eye-empty',
      'aiProviderAdmin.enable'
    )

    const modelEnableButton = wrapper
      .find('.ai-provider-model__actions')
      .findAll('button')[2]
    expectIconAction(
      modelEnableButton,
      'iconoir-eye-empty',
      'aiProviderAdmin.enable'
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
        .findAll('button')[0]
        .attributes('disabled')
    ).toBeDefined()
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
