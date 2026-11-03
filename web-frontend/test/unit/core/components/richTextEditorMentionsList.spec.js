import { shallowMount } from '@vue/test-utils'
import RichTextEditorMentionsList from '@baserow/modules/core/components/editor/RichTextEditorMentionsList'

it('keeps Subject IDs out of User mentions', () => {
  const command = vi.fn()
  const wrapper = shallowMount(RichTextEditorMentionsList, {
    props: {
      query: '',
      command,
      users: [
        { user_id: 1, name: 'Human' },
        { user_id: 2, name: 'Agent', type: 'core.Agent' },
        { id: 3, name: 'Retained Subject', type: 'auth.User' },
      ],
    },
  })
  expect(wrapper.html()).toMatchSnapshot()
  wrapper.vm.selectItem(0)
  expect(command).toHaveBeenCalledWith({ id: 1, label: 'Human' })
  command.mockClear()
  wrapper.vm.filteredUsers = [{ user_id: 2, name: 'Agent', type: 'core.Agent' }]
  wrapper.vm.selectItem(0)
  expect(command).not.toHaveBeenCalled()
})
