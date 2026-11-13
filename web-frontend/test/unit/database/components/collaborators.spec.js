import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditFieldMultipleCollaborators from '@baserow/modules/database/components/row/RowEditFieldMultipleCollaborators'
import FieldCollaboratorDropdown from '@baserow/modules/database/components/field/FieldCollaboratorDropdown'
import RowCardFieldMultipleCollaborators from '@baserow/modules/database/components/card/RowCardFieldMultipleCollaborators'

describe('Identity collaborators', () => {
  let testApp
  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      users: [{ id: 10, user_id: 20, name: 'Person' }],
      identities: [{ id: 30, user_id: 30, name: 'Ops' }],
    })
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  test('the picker groups Identities and emits their user id', async () => {
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
      'fieldmultipleCollaboratorsDropdown.identities'
    )
    const options = wrapper.findAll('.select-collaborators__dropdown-link')
    expect(
      options.map((option) =>
        option.find('.select-collaborators__dropdown-option').text()
      )
    ).toEqual(['Person', 'Ops'])
    expect(options[1].find('.iconoir-lock').exists()).toBe(true)
    await options[1].trigger('click')
    expect(wrapper.emitted('input')[0]).toEqual([30])
  })

  test('chips show the Identity icon and update its name after a rename', async () => {
    const wrapper = await testApp.mount(RowCardFieldMultipleCollaborators, {
      props: { value: [{ id: 30, name: 'Old name' }] },
    })
    expect(wrapper.find('.iconoir-lock').exists()).toBe(true)
    expect(wrapper.text()).toBe('Ops')
    testApp.store.commit('workspace/UPSERT_WORKSPACE_IDENTITY', {
      workspaceId: 1,
      identity: { id: 30, user_id: 30, name: 'Support' },
    })
    await nextTick()
    expect(wrapper.text()).toBe('Support')
  })

  test('an open row picker follows Identity creation, rename and removal', async () => {
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
          include_identities: true,
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
    testApp.store.commit('workspace/UPSERT_WORKSPACE_IDENTITY', {
      workspaceId: 1,
      identity: { id: 40, user_id: 40, name: 'New Identity' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('New Identity')
    testApp.store.commit('workspace/UPSERT_WORKSPACE_IDENTITY', {
      workspaceId: 1,
      identity: { id: 40, user_id: 40, name: 'Renamed Identity' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Renamed Identity')
    expect(wrapper.text()).not.toContain('New Identity')
    testApp.store.commit('workspace/DELETE_WORKSPACE_IDENTITY', {
      workspaceId: 1,
      identityId: 40,
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Renamed Identity')
  })

  test('a row picker hides Identities unless the field includes them', async () => {
    const wrapper = await testApp.mount(RowEditFieldMultipleCollaborators, {
      props: {
        field: { type: 'multiple_collaborators', include_identities: false },
        workspaceId: 1,
        value: [],
        readOnly: false,
      },
    })
    await wrapper.find('.button-text').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Person')
    expect(wrapper.text()).not.toContain('Ops')
  })

  test('a public picker recognizes Identity options without workspace data', async () => {
    testApp.store.commit('workspace/SET_ITEMS', [])
    const wrapper = await testApp.mount(FieldCollaboratorDropdown, {
      props: {
        collaborators: [{ id: 30, name: 'Ops', user_type: 'identity' }],
        showEmptyValue: false,
      },
    })
    await wrapper.find('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(wrapper.find('.select-collaborators__group').exists()).toBe(true)
    expect(wrapper.find('.iconoir-lock').exists()).toBe(true)
  })

  test('public chips identify Identities from the field options', async () => {
    testApp.store.commit('workspace/SET_ITEMS', [])
    const wrapper = await testApp.mount(RowCardFieldMultipleCollaborators, {
      props: {
        value: [{ id: 30, name: 'Ops' }],
        field: {
          available_collaborators: [
            { id: 30, name: 'Ops', user_type: 'identity' },
          ],
        },
      },
    })
    expect(wrapper.find('.iconoir-lock').exists()).toBe(true)
    expect(wrapper.text()).toBe('Ops')
  })
})
