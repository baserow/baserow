import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'
import TemplateInstall from '@baserow/modules/core/components/template/TemplateInstall'

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

  test('shows the description only when the template has one', async () => {
    let wrapper = await mountComponent({
      template: { ...template, description: 'Track projects.' },
    })
    expect(wrapper.find('.template-details__description').text()).toBe(
      'Track projects.'
    )

    wrapper = await mountComponent()
    expect(wrapper.find('.template-details__description').exists()).toBe(false)
  })

  test('lists the applications by order and switches the selection', async () => {
    const wrapper = await mountComponent()

    expect(applicationNames(wrapper)).toEqual(['First', 'Second'])
    // The preview opens the first application with a page, in API order.
    expect(selectedTables(wrapper)).toEqual(['Second table'])

    await wrapper.findAll('.tree__link')[0].trigger('click')

    expect(selectedTables(wrapper)).toEqual(['First table'])
  })

  test('installs a user template', async () => {
    const wrapper = await mountComponent({
      template: { ...template, type: 'user' },
    })

    expect(wrapper.find('.template-details__foot').exists()).toBe(true)
    expect(wrapper.find('.template-install').exists()).toBe(true)

    await wrapper
      .find('.template-install__actions .button-icon')
      .trigger('click')
    const links = wrapper.findAll('.context__menu-item-link')
    expect(links).toHaveLength(1)
    expect(links[0].text()).toContain('templateInstall.copyLink')
  })

  test('adds the owner actions to the install menu of an own template', async () => {
    const userTemplate = { ...template, type: 'user' }
    const wrapper = await mountComponent({
      template: userTemplate,
      isOwn: true,
    })
    expect(wrapper.find('.template-install__use').exists()).toBe(true)

    await wrapper
      .find('.template-install__actions .button-icon')
      .trigger('click')
    const links = wrapper.findAll('.context__menu-item-link')
    expect(links.map((link) => link.text())).toStrictEqual([
      'templateDetails.editDetails',
      'templateDetails.updateContent',
      'templateDetails.delete',
    ])

    await links[0].trigger('click')
    await links[1].trigger('click')

    expect(wrapper.emitted('edit')).toStrictEqual([['details'], ['content']])

    const items = wrapper.findAll('.context__menu-item')
    const last = items[items.length - 1]
    expect(last.classes()).toContain('context__menu-item--with-separator')
    const link = last.find('.context__menu-item-link--delete')
    expect(link.find('i').classes()).toContain('iconoir-bin')

    await link.trigger('click')

    expect(wrapper.emitted('delete')).toStrictEqual([[userTemplate]])
  })

  test('installs the latest revision only of an own template', async () => {
    const userTemplate = { ...template, type: 'user' }
    const other = await mountComponent({ template: userTemplate })
    expect(other.findComponent(TemplateInstall).props('latest')).toBe(false)

    const own = await mountComponent({ template: userTemplate, isOwn: true })
    expect(own.findComponent(TemplateInstall).props('latest')).toBe(true)
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
