import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import RowEditFieldAI from '@baserow_premium/components/row/RowEditFieldAI'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'

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

  test('Generate button is disabled when the selected model is ineligible for AI Fields', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', {
      ...workspace,
      ai_features: { ai_fields: { models: {} } },
    })

    const wrapper = await mountComponent(aiField)

    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  const mountWithValue = (field, value, props = {}) =>
    testApp.mount(RowEditFieldAI, {
      props: {
        field,
        value,
        readOnly: false,
        workspaceId: workspace.id,
        ...props,
      },
      global: {
        stubs: {
          RichTextEditorBubbleMenu: true,
          RichTextEditorFloatingMenu: true,
        },
      },
    })

  test('forwards the value edited in the inner field', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const wrapper = await mountWithValue(aiField, 'old')
    const textarea = wrapper.find('textarea')

    await textarea.trigger('focus')
    await textarea.setValue('new')
    await textarea.trigger('blur')

    expect(wrapper.emitted('update')).toEqual([['new', 'old']])
  })

  test('forwards the touched event of the inner field', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const wrapper = await mountWithValue(aiField, 'old', { touched: false })

    await wrapper.find('textarea').trigger('blur')

    expect(wrapper.emitted('touched')).toHaveLength(1)
  })

  test.each([
    [
      'plain text',
      { ...aiField, long_text_enable_rich_text: false },
      'Yes',
      'textarea',
    ],
    [
      'choice',
      {
        ...aiField,
        ai_output_type: 'choice',
        long_text_enable_rich_text: true,
        select_options: [{ id: 1, value: 'Yes', color: 'green' }],
      },
      { id: 1, value: 'Yes', color: 'green' },
      '.dropdown',
    ],
  ])(
    'passes no rich text props to the %s output field',
    async (outputName, field, value, inputSelector) => {
      await testApp.getStore().dispatch('workspace/forceCreate', workspace)

      const wrapper = await mountWithValue(field, value)

      expect(wrapper.find(inputSelector).exists()).toBe(true)
      expect(wrapper.html()).not.toMatch(/enable-?(mentions|images)/i)
    }
  )

  test('edits a rich text value without user mentions or images', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', {
      ...workspace,
      users: [{ user_id: 5, name: 'Jane Doe' }],
    })
    const wrapper = await mountWithValue(
      { ...aiField, long_text_enable_rich_text: true },
      '**bold** @5'
    )
    const editor = wrapper.findComponent(RichTextEditor)

    expect(wrapper.find('.tiptap strong').text()).toBe('bold')
    expect(wrapper.find('.tiptap .rich-text-editor__mention').exists()).toBe(
      false
    )
    expect(wrapper.find('.tiptap').text()).toBe('bold @5')
    expect(editor.props('mentionableUsers')).toBeNull()
    expect(editor.props('enableImages')).toBe(false)
    expect(editor.props('uploadFile')).toBeNull()

    editor.vm.$emit('focus')
    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    const [[newValue, oldValue]] = wrapper.emitted('update')
    expect(oldValue).toBe('**bold** @5')
    expect(newValue).toContain('**bold** @5')
  })

  test('keeps image markdown of a rich text value as text', async () => {
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const value = 'see ![x](https://example.com/a.png)'
    const wrapper = await mountWithValue(
      { ...aiField, long_text_enable_rich_text: true },
      value
    )
    const editor = wrapper.findComponent(RichTextEditor)

    expect(wrapper.find('.tiptap').text()).toBe(value)
    expect(wrapper.find('.tiptap img').exists()).toBe(false)

    editor.vm.$emit('focus')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update')).toBeUndefined()

    editor.vm.$emit('focus')
    editor.vm.focus()
    editor.vm.editor.commands.insertContent(' edited')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update')).toEqual([
      [String.raw`see !\[x\](https://example.com/a.png) edited`, value],
    ])
  })
})
