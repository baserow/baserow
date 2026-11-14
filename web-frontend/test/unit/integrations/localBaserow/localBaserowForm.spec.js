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

  async function mountComponent(defaultValues = {}) {
    return await testApp.mount(LocalBaserowForm, {
      props: {
        application: { id: 2, workspace: { id: 1 } },
        defaultValues,
      },
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
})
