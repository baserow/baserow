import { TestApp } from '@baserow/test/helpers/testApp'
import RowHistoryFieldRichText from '@baserow/modules/database/components/row/RowHistoryFieldRichText'

describe('RowHistoryFieldRichText component', () => {
  let testApp = null

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 10,
      name: 'Workspace',
      users: [{ user_id: 5, name: 'Jane Doe' }],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (entry) =>
    testApp.mount(RowHistoryFieldRichText, {
      props: {
        workspaceId: 10,
        entry,
        fieldIdentifier: 'field_1',
      },
      global: {
        stubs: {
          RichTextEditorBubbleMenu: true,
          RichTextEditorFloatingMenu: true,
        },
      },
    })

  test('renders read-only before and after values', async () => {
    const wrapper = await mountComponent({
      before: { field_1: '# Old title' },
      after: { field_1: '# New title' },
    })

    const removed = wrapper.find('.row-history-entry__diff--removed')
    const added = wrapper.find('.row-history-entry__diff--added')
    expect(removed.find('h1').text()).toBe('Old title')
    expect(added.find('h1').text()).toBe('New title')
    wrapper.findAll('.tiptap').forEach((editor) => {
      expect(editor.attributes('contenteditable')).toBe('false')
    })
  })

  test('renders only the added side when the value was empty before', async () => {
    const wrapper = await mountComponent({
      before: { field_1: '' },
      after: { field_1: 'added content' },
    })

    expect(wrapper.find('.row-history-entry__diff--removed').exists()).toBe(
      false
    )
    expect(wrapper.find('.row-history-entry__diff--added').text()).toBe(
      'added content'
    )
  })
})
