import { defineComponent, h } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import GridViewFieldAI from '@baserow_premium/components/views/grid/fields/GridViewFieldAI'
import GridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRichText'
import FieldRichTextModal from '@baserow/modules/database/components/view/FieldRichTextModal'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import RichTextEditorBubbleMenu from '@baserow/modules/core/components/editor/RichTextEditorBubbleMenu'

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

      const wrapper = await testApp.mount(GridViewFieldAI, {
        props: {
          field,
          value,
          selected: false,
          readOnly: false,
          storePrefix: '',
          workspaceId: workspace.id,
        },
      })

      expect(wrapper.text()).toContain('Yes')
      expect(wrapper.html()).not.toMatch(/enable-?(mentions|images)/i)
    }
  )

  test.each([
    ['plain', false],
    ['rich', true],
  ])(
    'hides Regenerate on a %s text cell once regeneration has finished',
    async (outputName, richText) => {
      const store = testApp.getStore()
      await store.dispatch('workspace/forceCreate', workspace)
      testApp.mock
        .onPost('/database/fields/1/generate-ai-field-values/')
        .reply(200, {})
      const field = { ...aiField, long_text_enable_rich_text: richText }
      // generate() reads the row from its parent, as GridViewCell provides it.
      const GridViewCell = defineComponent({
        props: { value: { type: String, default: null } },
        data: () => ({ row: { id: 1 } }),
        render() {
          return h(GridViewFieldAI, {
            field,
            value: this.value,
            row: this.row,
            selected: true,
            readOnly: false,
            storePrefix: 'page/',
            workspaceId: workspace.id,
          })
        },
      })
      const wrapper = await testApp.mount(GridViewCell, {
        props: { value: 'old' },
      })
      const aiCell = wrapper.findComponent(GridViewFieldAI)
      aiCell.vm.$refs.cell.edit(null, new MouseEvent('dblclick'))
      await flushPromises()

      await wrapper.find('.button-text').trigger('mousedown')
      await flushPromises()
      expect(aiCell.vm.generating).toBe(true)

      await store.dispatch('page/view/grid/setPendingFieldOperations', {
        fieldId: field.id,
        rowIds: [1],
        value: false,
      })
      await wrapper.setProps({ value: 'new' })
      await flushPromises()

      expect(aiCell.vm.$refs.cell.editing).toBe(false)
      expect(wrapper.text()).toContain('new')
      expect(wrapper.text()).not.toContain('gridViewFieldAI.regenerate')
    }
  )

  describe('rich text output', () => {
    const richField = { ...aiField, long_text_enable_rich_text: true }

    beforeEach(async () => {
      await testApp.getStore().dispatch('workspace/forceCreate', {
        ...workspace,
        users: [{ user_id: 5, name: 'Jane Doe' }],
      })
    })

    const mountSelected = () =>
      testApp.mount(GridViewFieldAI, {
        props: {
          field: richField,
          value: 'ping @5',
          selected: true,
          readOnly: false,
          storePrefix: '',
          workspaceId: workspace.id,
        },
        // The real teleport puts the modal outside the cell, as in the app.
        global: { stubs: { Teleport: false } },
      })

    const editInline = async (wrapper) => {
      const cell = wrapper.findComponent(GridViewFieldRichText)
      cell.vm.edit()
      await flushPromises()
      return cell
    }

    const expandIntoModal = async (cell) => {
      cell.vm.$refs.expandedModal.toggle()
      await flushPromises()
      return cell.vm.$refs.expandedModal.getTeleportedElement()
    }

    const click = (element) => {
      element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
      element.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    }

    test('mounts the rich text cell and offers Regenerate while editing', async () => {
      const wrapper = await mountSelected()

      expect(wrapper.findComponent(GridViewFieldRichText).exists()).toBe(true)
      expect(wrapper.text()).not.toContain('gridViewFieldAI.regenerate')

      await editInline(wrapper)

      expect(wrapper.text()).toContain('gridViewFieldAI.regenerate')
    })

    test('keeps user mentions and images out of the editors', async () => {
      const wrapper = await mountSelected()

      expect(wrapper.find('.rich-text-editor__mention').exists()).toBe(false)
      expect(wrapper.text()).toContain('ping @5')

      const cell = await editInline(wrapper)
      expect(cell.props('enableMentions')).toBe(false)
      expect(cell.props('enableImages')).toBe(false)
      const inline = cell.findComponent(RichTextEditor)
      const modal = cell.findComponent(FieldRichTextModal)
      expect(inline.props('mentionableUsers')).toBeNull()
      expect(inline.props('enableImages')).toBe(false)
      expect(inline.props('uploadFile')).toBeNull()
      expect(modal.props('mentionableUsers')).toBeNull()
      expect(modal.props('enableImages')).toBe(false)
      expect(modal.props('uploadFile')).toBeNull()
    })

    test('keeps image markdown as text and saves it only when edited', async () => {
      const value = 'see ![x](https://example.com/a.png)'
      const wrapper = await testApp.mount(GridViewFieldAI, {
        props: {
          field: richField,
          value,
          selected: true,
          readOnly: false,
          storePrefix: '',
          workspaceId: workspace.id,
        },
      })

      expect(wrapper.text()).toContain(value)
      expect(wrapper.find('.iconoir-media-image').exists()).toBe(false)

      let cell = await editInline(wrapper)
      expect(cell.find('.tiptap').text()).toBe(value)
      cell.vm.save()
      expect(wrapper.emitted('update')).toBeUndefined()

      cell = await editInline(wrapper)
      cell.vm.$refs.input.focus()
      cell.vm.$refs.input.editor.commands.insertContent(' edited')
      await flushPromises()
      cell.vm.save()

      expect(wrapper.emitted('update')).toEqual([
        [String.raw`see !\[x\](https://example.com/a.png) edited`, value],
      ])
    })

    test('stays selected when clicking inside the expanded modal', async () => {
      const wrapper = await mountSelected()
      const cell = await editInline(wrapper)
      const modal = await expandIntoModal(cell)

      click(modal.querySelector('.rich-text-modal'))

      expect(wrapper.emitted('unselect')).toBeUndefined()
      expect(cell.vm.isModalOpen()).toBe(true)
    })

    test('stays selected when clicking inside the inline editor menu', async () => {
      const wrapper = await mountSelected()
      const cell = await editInline(wrapper)
      // The editor moves its bubble menu to the body when showing it.
      const menu = cell.findComponent(RichTextEditorBubbleMenu).element
      document.body.appendChild(menu)

      click(menu)
      menu.remove()

      expect(wrapper.emitted('unselect')).toBeUndefined()
    })

    test('stays selected when the expanded modal is closed by a click', async () => {
      const wrapper = await mountSelected()
      const cell = await editInline(wrapper)
      const modal = await expandIntoModal(cell)

      click(modal)
      await flushPromises()

      expect(cell.vm.isModalOpen()).toBe(false)
      expect(wrapper.emitted('unselect')).toBeUndefined()
    })

    test('unselects once when clicking outside the inline editor', async () => {
      const wrapper = await mountSelected()
      await editInline(wrapper)

      click(document.body)

      // The inner cell also listens, but only the wrapper's `unselect` reaches the grid.
      expect(wrapper.emitted('unselect')).toHaveLength(1)
    })
  })
})
