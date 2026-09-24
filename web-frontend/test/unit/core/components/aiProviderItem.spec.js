import AIProviderItem from '@baserow/modules/core/components/ai/AIProviderItem'
import AIProviderActionsMenu from '@baserow/modules/core/components/ai/AIProviderActionsMenu'
import { TestApp } from '@baserow/test/helpers/testApp'

function expectMenuAction(menu, action, icon, label) {
  const item = menu.find(`[data-action="${action}"]`)
  expect(item.exists()).toBe(true)
  expect(item.find(`.${icon}`).exists()).toBe(true)
  expect(item.text()).toBe(label)
}

async function openMenu(menu) {
  await menu.find('button').trigger('click')
  await menu.vm.$nextTick()
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
    const modelName = wrapper.find('.ai-provider-model__name')
    expect(modelName.text()).toBe('gpt-5.6')
    expect(modelName.element.tagName).toBe('SPAN')
    expect(
      wrapper
        .find('.ai-provider-card__actions')
        .findAll('button')
        .map((button) => button.text())
    ).toEqual([''])

    const providerMenu = wrapper
      .find('.ai-provider-card__actions')
      .findComponent(AIProviderActionsMenu)
    await openMenu(providerMenu)
    expect(providerMenu.findAll('[data-action]')).toHaveLength(5)
    expectMenuAction(
      providerMenu,
      'add-model',
      'iconoir-plus',
      'aiProviderAdmin.addModel'
    )
    expectMenuAction(
      providerMenu,
      'test',
      'iconoir-play',
      'aiProviderAdmin.testAllModels'
    )
    expectMenuAction(providerMenu, 'edit', 'iconoir-edit', 'action.edit')
    expectMenuAction(
      providerMenu,
      'toggle',
      'iconoir-eye-off',
      'aiProviderAdmin.disable'
    )
    expectMenuAction(providerMenu, 'delete', 'iconoir-bin', 'action.delete')
    expect(providerMenu.find('[data-action="delete"]').classes()).toContain(
      'context__menu-item-link--delete'
    )
    const providerMenuTrigger = providerMenu.find('button')
    expect(providerMenuTrigger.attributes('title')).toBe(
      'aiProviderAdmin.moreActions'
    )
    expect(providerMenuTrigger.attributes('aria-label')).toBe(
      'aiProviderAdmin.moreActions'
    )

    await providerMenu.find('[data-action="test"]').trigger('click')
    expect(wrapper.emitted('test-all-models')).toEqual([
      [expect.objectContaining({ id: 1 })],
    ])
    await providerMenu.find('[data-action="add-model"]').trigger('click')
    expect(wrapper.emitted('add-model')).toEqual([
      [expect.objectContaining({ id: 1 })],
    ])

    const modelActions = wrapper.find('.ai-provider-model__actions')
    const modelActionButtons = modelActions.findAll('button')
    expect(modelActionButtons).toHaveLength(1)
    const modelMenu = modelActions.findComponent(AIProviderActionsMenu)
    await openMenu(modelMenu)
    expect(modelMenu.findAll('[data-action]')).toHaveLength(4)
    expectMenuAction(
      modelMenu,
      'test',
      'iconoir-play',
      'aiProviderAdmin.testModel'
    )
    expectMenuAction(modelMenu, 'edit', 'iconoir-edit', 'action.edit')
    expectMenuAction(
      modelMenu,
      'toggle',
      'iconoir-eye-off',
      'aiProviderAdmin.disable'
    )
    expectMenuAction(modelMenu, 'delete', 'iconoir-bin', 'action.delete')

    await providerMenu.find('[data-action="edit"]').trigger('click')
    expect(wrapper.emitted('edit-provider')).toEqual([
      [expect.objectContaining({ id: 1 })],
    ])
    await modelMenu.find('[data-action="edit"]').trigger('click')
    expect(wrapper.emitted('edit-model')).toEqual([
      [expect.objectContaining({ id: 1 }), expect.objectContaining({ id: 2 })],
    ])
    await modelMenu.find('[data-action="test"]').trigger('click')
    expect(wrapper.emitted('test-model')).toEqual([
      [expect.objectContaining({ id: 2 })],
    ])
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

    const providerMenu = wrapper
      .find('.ai-provider-card__actions')
      .findComponent(AIProviderActionsMenu)
    await openMenu(providerMenu)
    expect(providerMenu.findAll('[data-action]')).toHaveLength(5)
    expectMenuAction(
      providerMenu,
      'toggle',
      'iconoir-eye-empty',
      'aiProviderAdmin.enable'
    )

    const modelMenu = wrapper
      .find('.ai-provider-model__actions')
      .findComponent(AIProviderActionsMenu)
    await openMenu(modelMenu)
    expectMenuAction(
      modelMenu,
      'toggle',
      'iconoir-eye-empty',
      'aiProviderAdmin.enable'
    )
  })

  test('omits the provider test action when there are no models', async () => {
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

    const providerMenu = wrapper
      .find('.ai-provider-card__actions')
      .findComponent(AIProviderActionsMenu)
    await openMenu(providerMenu)

    expect(providerMenu.find('[data-action="test"]').exists()).toBe(false)
    expect(providerMenu.find('[data-action="add-model"]').exists()).toBe(true)
  })

  test('offers no menu on an inherited provider left without models', async () => {
    const wrapper = await testApp.mount(AIProviderItem, {
      props: {
        provider: {
          id: 1,
          provider_type: 'mistral',
          is_active: true,
          read_only: true,
          workspace_enabled: true,
          models: [],
        },
      },
    })

    expect(wrapper.find('.ai-provider-card__empty').exists()).toBe(true)
    expect(
      wrapper.find('.ai-provider-card__actions').findAll('button')
    ).toHaveLength(0)
    expect(wrapper.findAll('[data-action]')).toHaveLength(0)
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

    const providerMenuButton = wrapper
      .find('.ai-provider-card__actions')
      .find('button')
    const modelMenuButton = wrapper
      .find('.ai-provider-model__actions')
      .find('button')

    expect(providerMenuButton.attributes('disabled')).toBeDefined()
    expect(modelMenuButton.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.ai-provider-model__testing').text()).toBe(
      'aiProviderAdmin.testing'
    )
    expect(wrapper.find('.ai-provider-model__status').attributes('role')).toBe(
      'status'
    )
    expect(
      wrapper.find('.ai-provider-model__status').attributes('aria-live')
    ).toBe('polite')
  })

  test('shows compact test statuses and the full failure error in a tooltip', async () => {
    const error = 'The complete provider error returned by the API.'
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
              last_test_status: 'failure',
              last_test_error: error,
            },
            {
              id: 3,
              model_identifier: 'gpt-5.6-mini',
              is_enabled: true,
              last_test_status: 'success',
            },
            {
              id: 4,
              model_identifier: 'gpt-5.6-nano',
              is_enabled: true,
              last_test_status: null,
            },
          ],
        },
      },
    })

    const statuses = wrapper.findAll('.ai-provider-model__status')
    const failed = statuses[0].find('.ai-provider-model__test-failed')

    expect(statuses.map((status) => status.text())).toEqual([
      'aiProviderAdmin.testFailed',
      'aiProviderAdmin.testPassed',
      'aiProviderAdmin.notTested',
    ])
    expect(wrapper.text()).not.toContain(error)
    expect(failed.find('.iconoir-warning-circle').exists()).toBe(true)
    expect(statuses[1].find('.iconoir-check-circle').exists()).toBe(true)

    await failed.trigger('mouseenter')
    expect(document.querySelector('.tooltip__content').textContent).toBe(error)
  })

  test('shows a compact partial failure and feature details in the tooltip', async () => {
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
              feature_types: ['ai_fields', 'kuma'],
              last_test_status: 'failure',
              last_test_error:
                'The model did not call the compatibility test tool.',
              last_test_feature_results: [
                { feature_type: 'ai_fields', status: 'success', error: '' },
                {
                  feature_type: 'kuma',
                  status: 'failure',
                  error: 'The model did not call the compatibility test tool.',
                },
              ],
            },
          ],
        },
      },
    })

    const failed = wrapper.find('.ai-provider-model__test-failed')
    expect(failed.text()).toBe('aiProviderAdmin.someTestsFailed')

    await failed.trigger('mouseenter')
    expect(document.querySelector('.tooltip__content').textContent).toContain(
      'aiProviderAdmin.featureTestPassed'
    )
    expect(document.querySelector('.tooltip__content').textContent).toContain(
      'aiProviderAdmin.featureTestFailed'
    )
  })

  test('offers only the workspace toggle on an inherited provider', async () => {
    const provider = {
      id: 1,
      provider_type: 'openai',
      is_active: true,
      workspace_enabled: true,
      read_only: true,
      models: [
        {
          id: 2,
          model_identifier: 'gpt-5.6',
          is_enabled: true,
          last_test_status: null,
        },
      ],
    }
    const wrapper = await testApp.mount(AIProviderItem, {
      props: { provider },
    })

    expect(wrapper.text()).toContain('aiProviderAdmin.inherited')
    expect(wrapper.find('.badge--cyan').text()).toBe(
      'aiProviderAdmin.inherited'
    )
    expect(
      wrapper
        .find('.ai-provider-card__actions')
        .findAll('button')
        .map((button) => button.text())
    ).toEqual([''])
    // A test would spend the instance's credentials, so the row offers nothing.
    expect(
      wrapper.find('.ai-provider-model__actions').findAll('button')
    ).toHaveLength(0)

    const providerMenu = wrapper
      .find('.ai-provider-card__actions')
      .findComponent(AIProviderActionsMenu)
    await openMenu(providerMenu)
    expect(providerMenu.findAll('[data-action]')).toHaveLength(1)
    expectMenuAction(
      providerMenu,
      'toggle',
      'iconoir-eye-off',
      'aiProviderAdmin.disable'
    )

    await providerMenu.find('[data-action="toggle"]').trigger('click')
    expect(wrapper.emitted('toggle-provider')).toEqual([[provider]])
  })

  test('renders an embedded source badge and overridden model badge', async () => {
    const wrapper = await testApp.mount(AIProviderItem, {
      props: {
        provider: {
          id: 1,
          provider_type: 'openai',
          is_active: true,
          workspace_enabled: true,
          read_only: true,
          models: [
            {
              id: 2,
              model_identifier: 'gpt-5.6',
              is_enabled: true,
              last_test_status: null,
            },
          ],
        },
        embedded: true,
        hideActiveStatus: true,
        title: 'Instance',
        sourceLabel: 'Inherited',
        sourceColor: 'cyan',
        modelAnnotations: {
          2: {
            label: 'Overridden',
            tooltip: 'Overridden by workspace',
            muted: true,
          },
        },
      },
    })

    expect(wrapper.classes()).toContain('ai-provider-card--embedded')
    expect(wrapper.find('.ai-provider-card__title').element.tagName).toBe('H3')
    expect(wrapper.find('.badge--cyan').text()).toBe('Inherited')
    expect(wrapper.find('.badge--green').exists()).toBe(false)
    const annotation = wrapper.find('.ai-provider-model__annotation-badge')
    expect(annotation.classes()).toContain('badge--yellow')
    expect(annotation.text()).toBe('Overridden')
    expect(annotation.attributes('aria-label')).toBe('Overridden by workspace')
    const modelMenuButton = wrapper
      .find('.ai-provider-model__actions')
      .find('button')
    expect(modelMenuButton.exists()).toBe(true)
    expect(modelMenuButton.attributes('disabled')).toBeDefined()
    expect(modelMenuButton.attributes('title')).toBe('Overridden by workspace')

    await annotation.trigger('mouseenter')
    expect(document.querySelector('.tooltip__content').textContent).toBe(
      'Overridden by workspace'
    )
  })
})
