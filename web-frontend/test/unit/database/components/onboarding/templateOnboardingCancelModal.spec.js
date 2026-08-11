import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateOnboardingCancelModal from '@baserow/modules/database/components/onboarding/TemplateOnboardingCancelModal'
import TemplateImportForm from '@baserow/modules/database/components/onboarding/TemplateImportForm'
import { createTemplate } from '@baserow/test/unit/database/components/onboarding/helpers'

describe('TemplateOnboardingCancelModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const categories = [
    {
      id: 1,
      name: 'Category',
      templates: [
        createTemplate(1, 'First'),
        createTemplate(2, 'Second'),
        // Just like the real default template, this one doesn't have the `onboarding`
        // keyword.
        createTemplate(3, 'Default', { keywords: 'project', is_default: true }),
      ],
    },
  ]

  const mount = async (props = { categories }) => {
    const wrapper = await testApp.mount(TemplateOnboardingCancelModal, {
      propsData: { databaseStepType: 'template', ...props },
      // The modal content is teleported into the body, and the globally stubbed
      // teleport doesn't keep the content interactive.
      global: { stubs: { Teleport: false } },
    })
    await flushPromises()
    return wrapper
  }

  const templateItems = (wrapper) =>
    wrapper.findComponent(TemplateImportForm).findAll('.template-import-item')

  test('shows the default template first and selects it', async () => {
    const wrapper = await mount()

    const items = templateItems(wrapper)
    expect(items).toHaveLength(3)
    expect(items[0].text()).toBe('Default')
    expect(items[0].classes()).toContain('template-import-item--active')
    expect(items[1].classes()).not.toContain('template-import-item--active')
  })

  test('emits the selected template when continuing', async () => {
    const wrapper = await mount()

    await wrapper.findComponent({ name: 'Button' }).trigger('click')

    expect(wrapper.emitted().selected).toHaveLength(1)
    expect(wrapper.emitted().selected[0][0].type).toBe('template')
    expect(wrapper.emitted().selected[0][0].template.id).toBe(3)
  })

  test('emits the chosen template instead of the default one', async () => {
    const wrapper = await mount()

    await templateItems(wrapper)[1].trigger('click')
    await wrapper.findComponent({ name: 'Button' }).trigger('click')

    expect(wrapper.emitted().selected[0][0].template.id).toBe(1)
  })

  test('fills up to eight templates with the related categories', async () => {
    const wrapper = await mount({
      categories: [
        {
          id: 1,
          name: 'Related',
          templates: [
            createTemplate(1, 'Curated'),
            ...[2, 3, 4, 5, 6, 7, 8, 9].map((id) =>
              createTemplate(id, `Related ${id}`, { keywords: 'other' })
            ),
          ],
        },
        {
          id: 2,
          name: 'Unrelated',
          templates: [createTemplate(10, 'Unrelated', { keywords: 'other' })],
        },
      ],
    })

    const names = templateItems(wrapper).map((item) => item.text())
    expect(names).toHaveLength(8)
    expect(names[0]).toBe('Curated')
    expect(names).not.toContain('Unrelated')
  })
})
