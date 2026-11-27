import flushPromises from 'flush-promises'

import LocalBaserowForm from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowForm'
import { TestApp } from '@baserow/test/helpers/testApp'

const sections = (wrapper) =>
  wrapper.findAllComponents({ name: 'DropdownSection' }).map((section) => ({
    title: section.props('title'),
    items: section
      .findAllComponents({ name: 'DropdownItem' })
      .map((item) => [item.props('name'), item.props('description')]),
  }))

describe('LocalBaserowForm', () => {
  let testApp = null

  beforeEach(async () => {
    testApp = new TestApp()
    testApp.store.state.auth.user = { id: 1 }
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Acme',
      users: [],
    })
    testApp.mock.onGet('/identities/workspace/1/').reply(200, {
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 10, name: 'Writer identity', role_uid: 'MEMBER' },
        { id: 11, name: 'Reader identity', role_uid: 'UNKNOWN' },
      ],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(defaultValues = {}, mocks = {}) {
    return await testApp.mount(LocalBaserowForm, {
      props: {
        application: { id: 2, workspace: { id: 1 } },
        defaultValues,
      },
      global: { mocks },
    })
  }

  async function openDropdown(wrapper) {
    await wrapper.find('.dropdown__selected').trigger('click')
    await flushPromises()
  }

  async function selectItem(wrapper, name) {
    await wrapper
      .findAllComponents({ name: 'DropdownItem' })
      .find((item) => item.props('name') === name)
      .find('.select__item-link')
      .trigger('click')
    await flushPromises()
  }

  test('lists the current user and the identities in their sections', async () => {
    const wrapper = await mountComponent()
    await openDropdown(wrapper)

    expect(testApp.mock.history.get.at(-1).params).toEqual({
      page: 1,
      size: 100,
      for_selection: true,
    })
    // An identity whose role isn't one of the workspace roles has no
    // description.
    expect(sections(wrapper)).toEqual([
      {
        title: 'subjectType.members',
        items: [
          [
            'localBaserowForm.currentUser',
            'localBaserowForm.currentUserDescription',
          ],
        ],
      },
      {
        title: 'subjectType.identities',
        items: [
          ['Writer identity', 'localBaserowForm.identityRole'],
          ['Reader identity', null],
        ],
      },
    ])
  })

  test('offers no identities to a user who may not bind them', async () => {
    const wrapper = await mountComponent(
      {},
      { $hasPermission: (operation) => operation !== 'identity.update' }
    )
    await openDropdown(wrapper)

    expect(sections(wrapper).map(({ title }) => title)).toEqual([
      'subjectType.members',
    ])
    expect(testApp.mock.history.get).toEqual([])
  })

  test('tells when the workspace has no identities yet', async () => {
    testApp.mock
      .onGet('/identities/workspace/1/')
      .reply(200, { count: 0, next: null, previous: null, results: [] })
    const wrapper = await mountComponent()
    await openDropdown(wrapper)

    const identities = sections(wrapper)[1]
    expect(identities.items).toEqual([['localBaserowForm.noIdentities', null]])

    await selectItem(wrapper, 'localBaserowForm.noIdentities')

    expect(wrapper.emitted('values-changed')).toBeUndefined()
  })

  test('emits the selected identity as typed subject', async () => {
    const wrapper = await mountComponent()
    await openDropdown(wrapper)
    await selectItem(wrapper, 'Writer identity')

    expect(wrapper.find('.dropdown__selected-text').text()).toBe(
      'Writer identity'
    )
    expect(wrapper.emitted('values-changed').at(-1)[0]).toEqual({
      authorized_subject_id: 10,
      authorized_subject_type: 'auth.User',
    })
  })

  test('shows the saved identity as selected', async () => {
    const wrapper = await mountComponent({
      authorized_subject: {
        id: 11,
        type: 'auth.User',
        name: 'Reader identity',
      },
    })
    await flushPromises()

    expect(wrapper.find('.dropdown__selected-text').text()).toBe(
      'Reader identity'
    )
  })

  test('shows nothing selected for a saved trashed identity', async () => {
    const wrapper = await mountComponent({
      authorized_subject: {
        id: 11,
        type: 'auth.User',
        name: 'Reader identity',
        trashed: true,
      },
    })
    await flushPromises()

    expect(wrapper.find('.dropdown__selected-text').exists()).toBe(false)
    expect(wrapper.find('.dropdown__selected').text()).toBe('action.makeChoice')
  })

  test('shows the saved current user as selected', async () => {
    const wrapper = await mountComponent({
      authorized_subject: { id: 1, type: 'auth.User', first_name: 'Admin' },
    })
    await flushPromises()

    expect(wrapper.find('.dropdown__selected-text').text()).toBe(
      'localBaserowForm.currentUser'
    )
  })

  test('shows a saved different user by name', async () => {
    const wrapper = await mountComponent({
      authorized_subject: {
        id: 2,
        type: 'auth.User',
        first_name: 'Other user',
        username: 'other@example.com',
      },
    })
    await flushPromises()

    expect(wrapper.find('.dropdown__selected-text').text()).toBe('Other user')
    expect(
      wrapper.findComponent({ name: 'PaginatedDropdown' }).props('value')
    ).toBe('auth.User:2')
  })

  test('emits the current user as an explicit authorization subject', async () => {
    const wrapper = await mountComponent({
      authorized_subject: {
        id: 11,
        type: 'auth.User',
        name: 'Reader identity',
      },
    })
    await openDropdown(wrapper)
    await selectItem(wrapper, 'localBaserowForm.currentUser')

    expect(wrapper.emitted('values-changed').at(-1)[0]).toEqual({
      authorized_subject_id: 1,
      authorized_subject_type: 'auth.User',
    })
  })

  test('lists identities created elsewhere when opened again', async () => {
    const wrapper = await mountComponent()
    await openDropdown(wrapper)
    wrapper.findComponent({ name: 'PaginatedDropdown' }).vm.hide()

    testApp.mock.onGet('/identities/workspace/1/').reply(200, {
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 13, name: 'Other identity', role_uid: 'MEMBER' }],
    })
    await openDropdown(wrapper)

    expect(sections(wrapper)[1].items).toEqual([
      ['Other identity', 'localBaserowForm.identityRole'],
    ])
  })

  test('offers to add an identity from the dropdown footer', async () => {
    const wrapper = await mountComponent()
    await openDropdown(wrapper)

    const button = wrapper.find('.select__footer-button')
    expect(button.text()).toBe('localBaserowForm.addIdentity')

    const modal = wrapper.findComponent({ name: 'ManageIdentityModal' })
    const show = vi.spyOn(modal.vm, 'show').mockImplementation(() => {})
    await button.trigger('click')

    expect(show).toHaveBeenCalledOnce()
  })

  test('offers no identity creation to a user who may not create them', async () => {
    const wrapper = await mountComponent(
      {},
      { $hasPermission: (operation) => operation !== 'identity.create' }
    )
    await openDropdown(wrapper)

    expect(wrapper.find('.select__footer-button').exists()).toBe(false)
    expect(
      wrapper.findComponent({ name: 'ManageIdentityModal' }).exists()
    ).toBe(false)
  })

  test('selects the identity created from the dropdown', async () => {
    const wrapper = await mountComponent()
    await openDropdown(wrapper)
    await wrapper.find('.select__footer-button').trigger('click')

    testApp.mock.onGet('/identities/workspace/1/').reply(200, {
      count: 1,
      next: null,
      previous: null,
      results: [{ id: 12, name: 'New identity', role_uid: 'MEMBER' }],
    })
    const requestsBefore = testApp.mock.history.get.length
    wrapper
      .findComponent({ name: 'ManageIdentityModal' })
      .vm.$emit('saved', { id: 12, name: 'New identity' })
    await flushPromises()

    expect(wrapper.find('.dropdown__selected-text').text()).toBe('New identity')
    expect(wrapper.emitted('values-changed').at(-1)[0]).toEqual({
      authorized_subject_id: 12,
      authorized_subject_type: 'auth.User',
    })

    await openDropdown(wrapper)

    expect(testApp.mock.history.get.length).toBeGreaterThan(requestsBefore)
    expect(sections(wrapper)[1].items).toEqual([
      ['New identity', 'localBaserowForm.identityRole'],
    ])
  })
})
