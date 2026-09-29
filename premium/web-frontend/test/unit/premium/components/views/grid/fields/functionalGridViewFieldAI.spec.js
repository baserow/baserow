import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import FunctionalGridViewFieldAI from '@baserow_premium/components/views/grid/fields/FunctionalGridViewFieldAI'
import FunctionalGridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldRichText'

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

  test('disables generation when the selected model is ineligible for AI Fields', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', {
      ...workspace,
      ai_features: { ai_fields: { models: {} } },
    })

    const wrapper = await mountComponent(aiField)

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  test('renders a rich text value with mentions and images left as text', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', {
      ...workspace,
      users: [{ user_id: 5, name: 'Jane Doe' }],
    })

    const wrapper = await testApp.mount(FunctionalGridViewFieldAI, {
      props: {
        field: { ...aiField, long_text_enable_rich_text: true },
        row: { id: 1 },
        value: '**bold** @5 ![x](https://example.com/a.png)',
        state: {},
        readOnly: false,
        storePrefix: '',
        workspaceId: workspace.id,
      },
    })

    expect(wrapper.find('strong').text()).toBe('bold')
    expect(wrapper.find('.rich-text-editor__mention').exists()).toBe(false)
    expect(wrapper.find('.iconoir-media-image').exists()).toBe(false)
    expect(wrapper.text()).toBe('bold @5 ![x](https://example.com/a.png)')
    const cell = wrapper.findComponent(FunctionalGridViewFieldRichText)
    expect(cell.props('enableMentions')).toBe(false)
    expect(cell.props('enableImages')).toBe(false)
  })

  test.each([
    ['plain text', { ...aiField, long_text_enable_rich_text: false }, 'Yes'],
    [
      'choice',
      {
        ...aiField,
        ai_output_type: 'choice',
        long_text_enable_rich_text: true,
        select_options: [{ id: 1, value: 'Yes', color: 'green' }],
      },
      { id: 1, value: 'Yes', color: 'green' },
    ],
  ])(
    'passes no rich text props to the %s output cell',
    async (outputName, field, value) => {
      await testApp.getStore().dispatch('workspace/forceCreate', workspace)

      const wrapper = await testApp.mount(FunctionalGridViewFieldAI, {
        props: {
          field,
          row: { id: 1 },
          value,
          state: {},
          readOnly: false,
          storePrefix: '',
          workspaceId: workspace.id,
        },
      })

      expect(wrapper.text()).toContain('Yes')
      expect(wrapper.html()).not.toMatch(/enable-?(mentions|images)/i)
    }
  )
})
