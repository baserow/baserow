import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateImportForm from '@baserow/modules/database/components/onboarding/TemplateImportForm'

describe('TemplateImportForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const template = (id, name, extra = {}) => ({
    id,
    name,
    slug: name.toLowerCase(),
    icon: 'iconoir-table',
    keywords: 'onboarding',
    open_application: null,
    is_default: false,
    ...extra,
  })

  const categories = [
    {
      id: 1,
      name: 'Category',
      templates: [
        ...[1, 2, 3, 4, 5, 6, 7].map((id) => template(id, `Suggested ${id}`)),
        template(8, 'Default', { keywords: 'crm', is_default: true }),
        template(9, 'Application', { keywords: 'crm', open_application: 12 }),
      ],
    },
  ]

  const mount = async (props = {}) => {
    const wrapper = await testApp.mount(TemplateImportForm, {
      propsData: { providedCategories: categories, ...props },
    })
    await flushPromises()
    return wrapper
  }

  const names = (wrapper) =>
    wrapper.findAll('.template-import-item').map((item) => item.text())

  test('suggests the first six templates with the onboarding keyword', async () => {
    const wrapper = await mount()

    expect(names(wrapper)).toStrictEqual([
      'Suggested 1',
      'Suggested 2',
      'Suggested 3',
      'Suggested 4',
      'Suggested 5',
      'Suggested 6',
    ])
    expect(wrapper.emitted()['selected-template']).toBeUndefined()
  })

  test('searching also finds templates without the onboarding keyword', async () => {
    const wrapper = await mount()

    await wrapper.find('input').setValue('crm')

    // The template that must open an application is never shown.
    expect(names(wrapper)).toStrictEqual(['Default'])
  })
})
