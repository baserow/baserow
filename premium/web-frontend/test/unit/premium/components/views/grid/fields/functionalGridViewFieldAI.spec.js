import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import FunctionalGridViewFieldAI from '@baserow_premium/components/views/grid/fields/FunctionalGridViewFieldAI'

describe('FunctionalGridViewFieldAI component', () => {
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

  const mountComponent = (field) =>
    testApp.mount(FunctionalGridViewFieldAI, {
      props: {
        field,
        row: { id: 1 },
        value: null,
        state: {},
        readOnly: false,
        storePrefix: '',
        workspaceId: workspace.id,
      },
    })

  test('Generate button is disabled when the prompt is broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent({ ...aiField, error: 'boom' })

    // A real <button> (not an anchor) so the disabled attribute takes effect.
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  test('Generate button is enabled when the prompt is not broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent(aiField)

    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()
  })
})
