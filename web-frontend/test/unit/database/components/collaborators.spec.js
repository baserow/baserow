import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditFieldMultipleCollaborators from '@baserow/modules/database/components/row/RowEditFieldMultipleCollaborators'
import FieldCollaboratorDropdown from '@baserow/modules/database/components/field/FieldCollaboratorDropdown'
import RowCardFieldMultipleCollaborators from '@baserow/modules/database/components/card/RowCardFieldMultipleCollaborators'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import RichTextEditorMentionsList from '@baserow/modules/core/components/editor/RichTextEditorMentionsList'

describe('Agent collaborators', () => {
  let testApp
  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      users: [{ id: 10, user_id: 20, name: 'Person' }],
      agents: [{ id: 30, user_id: 30, name: 'Ops' }],
    })
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  test('the picker groups Agents and emits their user id', async () => {
    const wrapper = await testApp.mount(FieldCollaboratorDropdown, {
      props: {
        collaborators: [
          { id: 30, name: 'Ops' },
          { id: 20, name: 'Person' },
        ],
        showEmptyValue: false,
      },
    })
    await wrapper.find('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(wrapper.find('.select-collaborators__group').text()).toBe(
      'fieldmultipleCollaboratorsDropdown.agents'
    )
    const options = wrapper.findAll('.select-collaborators__dropdown-link')
    expect(
      options.map((option) =>
        option.find('.select-collaborators__dropdown-option').text()
      )
    ).toEqual(['Person', 'Ops'])
    expect(options[1].find('.baserow-icon-agent').exists()).toBe(true)
    await options[1].trigger('click')
    expect(wrapper.emitted('input')[0]).toEqual([30])
  })

  test('chips show the Agent icon and update its name after a rename', async () => {
    const wrapper = await testApp.mount(RowCardFieldMultipleCollaborators, {
      props: { value: [{ id: 30, name: 'Old name' }] },
    })
    expect(wrapper.find('.baserow-icon-agent').exists()).toBe(true)
    expect(wrapper.text()).toBe('Ops')
    testApp.store.commit('workspace/UPSERT_WORKSPACE_AGENT', {
      workspaceId: 1,
      agent: { id: 30, user_id: 30, name: 'Support' },
    })
    await nextTick()
    expect(wrapper.text()).toBe('Support')
  })

  test('an open row picker follows Agent creation, rename and removal', async () => {
    testApp.store.commit('workspace/ADD_WORKSPACE_USER', {
      workspaceId: 1,
      values: {
        id: 11,
        user_id: 21,
        name: 'Pending deletion',
        to_be_deleted: true,
      },
    })
    const wrapper = await testApp.mount(RowEditFieldMultipleCollaborators, {
      props: {
        field: {
          type: 'multiple_collaborators',
          available_collaborators: [{ id: 20, name: 'Person' }],
        },
        workspaceId: 1,
        value: [],
        readOnly: false,
      },
    })
    await wrapper.find('.button-text').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Ops')
    expect(wrapper.text()).not.toContain('Pending deletion')
    testApp.store.commit('workspace/UPSERT_WORKSPACE_AGENT', {
      workspaceId: 1,
      agent: { id: 40, user_id: 40, name: 'New Agent' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('New Agent')
    testApp.store.commit('workspace/UPSERT_WORKSPACE_AGENT', {
      workspaceId: 1,
      agent: { id: 40, user_id: 40, name: 'Renamed Agent' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Renamed Agent')
    expect(wrapper.text()).not.toContain('New Agent')
    testApp.store.commit('workspace/DELETE_WORKSPACE_AGENT', {
      workspaceId: 1,
      agentId: 40,
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Renamed Agent')
  })

  test('a public picker recognizes Agent options without workspace data', async () => {
    testApp.store.commit('workspace/SET_ITEMS', [])
    const wrapper = await testApp.mount(FieldCollaboratorDropdown, {
      props: {
        collaborators: [{ id: 30, name: 'Ops', agent: true }],
        showEmptyValue: false,
      },
    })
    await wrapper.find('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(wrapper.find('.select-collaborators__group').exists()).toBe(true)
    expect(wrapper.find('.baserow-icon-agent').exists()).toBe(true)
  })

  test('public chips identify Agents from the field options', async () => {
    testApp.store.commit('workspace/SET_ITEMS', [])
    const wrapper = await testApp.mount(RowCardFieldMultipleCollaborators, {
      props: {
        value: [{ id: 30, name: 'Ops' }],
        field: {
          available_collaborators: [{ id: 30, name: 'Ops', agent: true }],
        },
      },
    })
    expect(wrapper.find('.baserow-icon-agent').exists()).toBe(true)
    expect(wrapper.text()).toBe('Ops')
  })

  test('an open editor updates a renamed Agent mention without saving content', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: 'Ask @30',
        enableRichTextFormatting: true,
        mentionableUsers:
          testApp.store.getters['workspace/getCollaborators'](1),
      },
    })
    expect(wrapper.find('[data-type="mention"]').text()).toBe('@Ops')
    await wrapper.setProps({
      mentionableUsers: [{ user_id: 30, name: 'Support', agent: true }],
    })
    expect(wrapper.find('[data-type="mention"]').text()).toBe('@Support')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  test('the mention picker finds and selects an Agent', async () => {
    const command = vi.fn()
    const wrapper = await testApp.mount(RichTextEditorMentionsList, {
      props: {
        users: testApp.store.getters['workspace/getCollaborators'](1),
        query: 'ops',
        command,
      },
    })
    expect(wrapper.findAll('li')).toHaveLength(1)
    expect(wrapper.find('.baserow-icon-agent').exists()).toBe(true)
    await wrapper.find('li').trigger('click')
    expect(command).toHaveBeenCalledWith({ id: 30, label: 'Ops' })
  })
})
