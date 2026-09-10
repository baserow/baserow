import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import GridViewFieldAI from '@baserow_premium/components/views/grid/fields/GridViewFieldAI'

describe('GridViewFieldAI component', () => {
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
    testApp.mount(GridViewFieldAI, {
      props: {
        field,
        value: null,
        selected: false,
        readOnly: false,
        storePrefix: '',
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

  test('Enter key does not trigger generation when the prompt is broken', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const wrapper = await mountComponent({ ...aiField, error: 'boom' })

    // Selecting an empty cell and pressing Enter triggers `generate()`; the
    // broken prompt guard must stop it before any request is made.
    wrapper.vm.select()
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    await wrapper.vm.$nextTick()

    expect(testApp.mock.history.post).toHaveLength(0)
    wrapper.vm.beforeUnSelect()
  })
})
