import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { h } from 'vue'

import { TestApp } from '@baserow/test/helpers/testApp'
import { heldBack } from '@baserow/test/helpers/heldBack'
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
    vi.restoreAllMocks()
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

  test('opens another application when the preferred one is a hidden agent', async () => {
    testApp.mock.reset()
    testApp.mock
      .onGet(`/applications/workspace/${template.workspace_id}/`)
      .reply(200, [
        {
          id: 3,
          name: 'Ticket triage',
          order: 1,
          type: 'agent',
          workspace: { id: template.workspace_id },
        },
        {
          id: 1,
          name: 'Support',
          order: 2,
          type: 'database',
          workspace: { id: template.workspace_id },
          tables: [{ id: 10, name: 'Tickets', order: 1, database_id: 1 }],
        },
      ])
    vi.spyOn(
      testApp.$registry.get('application', 'agent'),
      'canBeCreated'
    ).mockReturnValue(false)
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template: { ...template, open_application: 3 } },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Ticket triage')
    expect(
      wrapper.findAll('.tree__sub-link').map((link) => link.text())
    ).toEqual(['Tickets'])
    expect(wrapper.find('table-template-stub').exists()).toBe(true)
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

  test("doesn't keep the table of the previous revision when the new one fails", async () => {
    const other = { ...template, workspace_id: template.workspace_id + 1 }
    testApp.mock
      .onGet(`/applications/workspace/${other.workspace_id}/`)
      .reply(500)
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()
    expect(wrapper.find('table-template-stub').exists()).toBe(true)

    await wrapper.setProps({ template: other })
    await flushPromises()

    expect(wrapper.find('table-template-stub').exists()).toBe(false)
  })

  test('shows the revision it shows now once an earlier one answers late', async () => {
    const other = { ...template, workspace_id: template.workspace_id + 1 }
    const late = heldBack()
    testApp.mock
      .onGet(`/applications/workspace/${other.workspace_id}/`)
      .replyOnce(late.reply)
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template: other },
      global: { stubs: { TableTemplate: true } },
    })

    await wrapper.setProps({ template })
    await flushPromises()
    late.send([200, []])
    await flushPromises()

    expect(wrapper.find('.loading-absolute-center').exists()).toBe(false)
    expect(
      wrapper.findAll('.tree__sub-link').map((link) => link.text())
    ).toEqual(['Second table'])
  })
})
