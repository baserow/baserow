import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { h } from 'vue'

import { TestApp } from '@baserow/test/helpers/testApp'
import {
  mockTemplateApplications,
  template,
} from '@baserow/test/fixtures/templates'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'

describe('TemplatePreview', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    mockTemplateApplications(testApp.mock)
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('switches the selected application in the default sidebar', async () => {
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()

    const selectedTables = () =>
      wrapper.findAll('.tree__sub-link').map((link) => link.text())

    expect(wrapper.find('.sidebar').exists()).toBe(true)
    expect(selectedTables()).toEqual(['Second table'])

    await wrapper.findAll('.tree__link')[0].trigger('click')

    expect(selectedTables()).toEqual(['First table'])
  })

  test('keeps the content of a new copy of the same template', async () => {
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()

    await wrapper.setProps({ template: { ...template, name: 'Renamed' } })
    await flushPromises()

    expect(testApp.mock.history.get).toHaveLength(1)
  })

  test('loads the content of a revision in another workspace', async () => {
    testApp.mock
      .onGet(`/applications/workspace/${template.workspace_id + 1}/`)
      .reply(200, [])
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()

    await wrapper.setProps({
      template: { ...template, workspace_id: template.workspace_id + 1 },
    })
    await flushPromises()

    expect(testApp.mock.history.get.map(({ url }) => url)).toEqual([
      `/applications/workspace/${template.workspace_id}/`,
      `/applications/workspace/${template.workspace_id + 1}/`,
    ])
  })

  test('keeps the sidebar while a revision in another workspace loads', async () => {
    testApp.mock
      .onGet(`/applications/workspace/${template.workspace_id + 1}/`)
      .reply(200, [])
    let mounts = 0
    const Sidebar = { mounted: () => mounts++, render: () => h('div') }
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template },
      slots: { sidebar: () => h(Sidebar) },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()

    await wrapper.setProps({
      template: { ...template, workspace_id: template.workspace_id + 1 },
    })
    await flushPromises()

    expect(mounts).toBe(1)
  })
})
