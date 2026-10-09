import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'

const template = {
  id: 5,
  slug: 'project-tracker',
  name: 'Project Tracker',
  workspace_id: 10,
  open_application: null,
}

const database = (id, name, order) => ({
  id,
  name,
  order,
  type: 'database',
  workspace: { id: 10 },
  tables: [{ id: id * 10, name: `${name} table`, order: 1, database_id: id }],
})

describe('TemplatePreview', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.mock
      .onGet(`/applications/workspace/${template.workspace_id}/`)
      .reply(200, [database(1, 'Second', 2), database(2, 'First', 1)])
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
})
