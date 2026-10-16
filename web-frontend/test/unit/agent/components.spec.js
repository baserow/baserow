import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentApplicationSidebar from '@baserow/modules/agent/components/AgentApplicationSidebar'

describe('AgentApplicationSidebar', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('renames the agent through the standard application context', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    const agent = { id: 10, name: 'Support agent', type: 'agent' }
    const application = await testApp.store.dispatch(
      'application/forceCreate',
      { ...agent, workspace: { id: 1 } }
    )
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    testApp.mock
      .onPatch('/applications/10/')
      .reply(200, { ...agent, name: 'Support assistant' })
    const wrapper = await testApp.mount(AgentApplicationSidebar, {
      props: {
        application,
        workspace: testApp.store.getters['workspace/get'](1),
      },
    })

    await wrapper.find('.tree__options').trigger('click')
    await flushPromises()
    await wrapper
      .findAll('.context__menu-item-link')
      .find((link) => link.text() === 'sidebarApplication.rename')
      .trigger('click')
    const editable = wrapper.find('[contenteditable="true"]')
    editable.element.textContent = 'Support assistant'
    await editable.trigger('input')
    await editable.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      name: 'Support assistant',
    })
    expect(wrapper.find('.tree__link').attributes('aria-label')).toBe(
      'Support assistant'
    )
  })
})
