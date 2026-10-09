import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'

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

describe('TemplateDetails', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    // Returned out of order, so the sidebar must sort them by `order`.
    testApp.mock
      .onGet(`/applications/workspace/${template.workspace_id}/`)
      .reply(200, [database(1, 'Second', 2), database(2, 'First', 1)])
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = async (props = {}) => {
    const wrapper = await testApp.mount(TemplateDetails, {
      props: { template, ...props },
      global: { stubs: { TableTemplate: true } },
    })
    await flushPromises()
    return wrapper
  }

  const applicationNames = (wrapper) =>
    wrapper.findAll('.tree__link-text').map((link) => link.text())

  const selectedTables = (wrapper) =>
    wrapper.findAll('.tree__sub-link').map((link) => link.text())

  test('replaces the default sidebar with the template details', async () => {
    const wrapper = await mountComponent({
      categories: [{ id: 1, name: 'Project management' }],
    })

    expect(wrapper.find('.sidebar').exists()).toBe(false)
    expect(wrapper.find('.layout__col-1').attributes('style')).toContain(
      'width: 320px'
    )
    expect(wrapper.find('.template-details__name').text()).toBe(
      'Project Tracker'
    )
    expect(
      wrapper.findAll('.template-details__category').map((c) => c.text())
    ).toEqual(['Project management'])
    expect(wrapper.find('.template-install').exists()).toBe(true)
  })

  test('lists the applications by order and switches the selection', async () => {
    const wrapper = await mountComponent()

    expect(applicationNames(wrapper)).toEqual(['First', 'Second'])
    // The preview opens the first application with a page, in API order.
    expect(selectedTables(wrapper)).toEqual(['Second table'])

    await wrapper.findAll('.tree__link')[0].trigger('click')

    expect(selectedTables(wrapper)).toEqual(['First table'])
  })

  test('shows the back link only when asked and emits back', async () => {
    const withoutBack = await mountComponent()
    expect(withoutBack.find('.template-details__back-link').exists()).toBe(
      false
    )

    const withBack = await mountComponent({ showBack: true })
    await withBack.find('.template-details__back-link').trigger('click')

    expect(withBack.emitted('back')).toHaveLength(1)
  })
})
