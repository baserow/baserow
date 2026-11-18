import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test, vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { registerRealtimeEvents } from '@baserow_enterprise/realtime'
import { EnterprisePlugin } from '@baserow_enterprise/plugins'
import ApplicationForm from '@baserow/modules/core/components/application/ApplicationForm'
import PersonalApplicationForm from '@baserow_enterprise/components/member-roles/PersonalApplicationForm'

async function mountForm(licensed) {
  const show = vi.fn()
  const wrapper = await mountSuspended(ApplicationForm, {
    props: {
      workspace: { id: 9 },
      loading: false,
      defaultValues: { name: 'Test app' },
    },
    global: {
      mocks: {
        $registry: {
          getAll: () => ({
            enterprise: {
              getType: () => 'enterprise',
              getApplicationCreateFormComponent: () => PersonalApplicationForm,
            },
          }),
        },
        $hasFeature: () => licensed,
      },
      stubs: {
        PaidFeaturesModal: {
          props: ['initialSelectedType', 'workspace'],
          methods: { show },
          template: '<span />',
        },
      },
    },
  })
  return { wrapper, show }
}

test('Personal adds a policy to the submitted application, Collaborative removes it', async () => {
  const { wrapper } = await mountForm(true)
  await wrapper.get('input[value="personal"]').trigger('click')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('submitted')[0][0]).toEqual({
    name: 'Test app',
    access_policy: 'personal',
  })
  await wrapper.get('input[value="collaborative"]').trigger('click')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('submitted')[1][0]).toEqual({ name: 'Test app' })
})

test('locked Personal opens the RBAC upgrade modal and leaves the form collaborative', async () => {
  const { wrapper, show } = await mountForm(false)
  const button = wrapper.get('button[type="button"]')
  expect(button.find('.iconoir-lock').exists()).toBe(true)
  await button.trigger('click')
  expect(show).toHaveBeenCalledOnce()
  expect(
    wrapper
      .getComponent(PersonalApplicationForm)
      .getComponent({ ref: 'upgrade' })
      .props()
  ).toMatchObject({ initialSelectedType: 'rbac', workspace: { id: 9 } })
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('submitted')[0][0]).toEqual({ name: 'Test app' })
})

test('the Personal indicator follows the stored policy, including after sharing', () => {
  const plugin = new EnterprisePlugin({ app: { $i18n: { t: (key) => key } } })
  expect(plugin.getApplicationSidebarIndicator({})).toBeNull()
  expect(
    plugin.getApplicationSidebarIndicator({ access_policy: 'personal' })
  ).toMatchObject({
    icon: 'iconoir-user',
    label: 'personalApplication.indicator',
  })
})

test('a permissions event reconciles visible apps and tables', async () => {
  const testApp = new TestApp()
  try {
    const { store, mock } = testApp
    const workspace = { id: 1, name: 'Workspace' }
    await store.dispatch('workspace/forceCreate', workspace)
    const agent = { id: 1, type: 'agent', name: 'Revoked agent', workspace }
    const database = {
      id: 2,
      type: 'database',
      name: 'Personal database',
      workspace,
      access_policy: 'personal',
      tables: [{ id: 1, name: 'Old table' }],
    }
    await store.dispatch('application/forceCreate', agent)
    await store.dispatch('application/forceCreate', database)
    const incoming = {
      ...agent,
      id: 3,
      name: 'Invited agent',
      access_policy: 'personal',
    }
    mock
      .onGet('/applications/workspace/1/')
      .reply(200, [
        incoming,
        { ...database, tables: [{ id: 2, name: 'Shared table' }] },
      ])
    mock.onGet().reply(200, [])
    const events = {}
    registerRealtimeEvents({
      registerEvent(name, callback) {
        events[name] = callback
      },
    })
    await events.permissions_updated({ store }, { workspace_id: 1 })
    expect(store.getters['application/get'](1)).toBeUndefined()
    expect(store.getters['application/get'](3)).toMatchObject(incoming)
    expect(
      store.getters['application/get'](2).tables.map(({ id }) => id)
    ).toEqual([2])
  } finally {
    await testApp.afterEach()
  }
})
