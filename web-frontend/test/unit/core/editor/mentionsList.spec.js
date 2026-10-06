import { mount } from '@vue/test-utils'

import RichTextEditorMentionsList from '@baserow/modules/core/components/editor/RichTextEditorMentionsList'

const users = [
  { user_id: 1, name: 'Ann' },
  { user_id: 2, name: 'Bob' },
]
const agents = [{ id: 10, name: 'Support agent' }]

function mountList(props = {}) {
  return mount(RichTextEditorMentionsList, {
    props: { users, agents: [], command: vi.fn(), query: '', ...props },
    global: { mocks: { $t: (key) => key } },
  })
}

describe('RichTextEditorMentionsList', () => {
  test('lists members only without agents, as before', () => {
    const wrapper = mountList()
    expect(
      wrapper
        .findAll('.rich-text-editor__mention-list-item')
        .map((i) => i.text())
    ).toEqual(['AAnn', 'BBob'])
    expect(
      wrapper.find('.rich-text-editor__mention-list-section').exists()
    ).toBe(false)
  })

  test('adds an agents section and inserts the mention with its kind', async () => {
    const command = vi.fn()
    const wrapper = mountList({ agents, command })
    expect(
      wrapper
        .findAll('.rich-text-editor__mention-list-section')
        .map((i) => i.text())
    ).toEqual(['richTextEditor.mentionMembers', 'richTextEditor.mentionAgents'])

    await wrapper
      .findAll('.rich-text-editor__mention-list-item')
      .at(2)
      .trigger('click')
    expect(command).toHaveBeenCalledWith({
      id: 10,
      label: 'Support agent',
      kind: 'application',
    })
    await wrapper
      .findAll('.rich-text-editor__mention-list-item')
      .at(0)
      .trigger('click')
    expect(command).toHaveBeenLastCalledWith({
      id: 1,
      label: 'Ann',
      kind: 'user',
    })
  })

  test('filters both lists by the query', async () => {
    const wrapper = mountList({ agents, query: 'sup' })
    expect(
      wrapper
        .findAll('.rich-text-editor__mention-list-item')
        .map((i) => i.text())
    ).toEqual(['Support agent'])
    await wrapper.setProps({ query: 'zzz' })
    expect(wrapper.find('.rich-text-editor__mention-list').exists()).toBe(false)
  })
})
