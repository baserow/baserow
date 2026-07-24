import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import RowEditFieldAI from '@baserow_premium/components/row/RowEditFieldAI'

describe('RowEditFieldAI component', () => {
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
    testApp.mount(RowEditFieldAI, {
      props: {
        field,
        value: null,
        readOnly: false,
        workspaceId: workspace.id,
      },
    })

  test('Generate button is disabled when the prompt is broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent({ ...aiField, error: 'boom' })

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  test('Generate button is enabled when the prompt is not broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent(aiField)

    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()
  })

  test('Generate button is disabled when the selected model is unavailable', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', {
      ...workspace,
      generative_ai_models_enabled: { openai: [] },
    })

    const wrapper = await mountComponent(aiField)

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })
})
