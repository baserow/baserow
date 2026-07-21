import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import GridViewFieldAIGenerateValuesContextItem from '@baserow_premium/components/views/grid/fields/GridViewFieldAIGenerateValuesContextItem'

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
        storePrefix: '',
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
})
