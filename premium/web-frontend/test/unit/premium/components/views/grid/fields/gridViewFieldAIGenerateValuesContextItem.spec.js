import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import GridViewFieldAIGenerateValuesContextItem from '@baserow_premium/components/views/grid/fields/GridViewFieldAIGenerateValuesContextItem'
import flushPromises from 'flush-promises'

describe('GridViewFieldAIGenerateValuesContextItem component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    testApp.giveCurrentUserGlobalPremiumFeatures()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const workspace = {
    id: 1,
    name: 'testWorkspace',
    generative_ai_models_enabled: { openai: ['gpt-4'] },
  }

  const aiField = {
    id: 1,
    name: 'AI field',
    order: 0,
    type: 'ai',
    primary: false,
    ai_generative_ai_type: 'openai',
    ai_generative_ai_model: 'gpt-4',
    ai_output_type: 'text',
    error: null,
  }

  const mountComponent = (field, getRows) =>
    testApp.mount(GridViewFieldAIGenerateValuesContextItem, {
      props: {
        field,
        getRows,
        storePrefix: 'page/',
        database: { workspace },
      },
    })

  test('item is disabled and does not fetch rows when the prompt is broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const getRows = vi.fn()

    const wrapper = await mountComponent({ ...aiField, error: 'boom' }, getRows)

    expect(wrapper.find('a').classes()).toContain('disabled')

    await wrapper.find('a').trigger('click')
    expect(getRows).not.toHaveBeenCalled()
    expect(testApp.mock.history.post).toHaveLength(0)
  })

  test('item is enabled when the prompt is not broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent(aiField, vi.fn())

    expect(wrapper.find('a').classes()).not.toContain('disabled')
  })

  test('model-unavailable response marks the field as errored and disables the item', async () => {
    const store = testApp.getStore()
    await store.dispatch('workspace/forceCreate', workspace)
    await store.dispatch('field/forceSetFields', {
      fields: [{ ...aiField }],
    })
    testApp.mock
      .onPost('/database/fields/1/generate-ai-field-values/')
      .reply(400, {
        error: 'ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE',
        detail: 'Untranslated backend detail',
      })
    const field = store.getters['field/get'](aiField.id)
    const wrapper = await mountComponent(field, async () => [{ id: 10 }])

    await wrapper.find('a').trigger('click')
    await flushPromises()

    expect(field.error).toBe(
      'clientHandler.modelDoesNotBelongToTypeDescription'
    )
    expect(wrapper.find('a').classes()).toContain('disabled')
  })
})
