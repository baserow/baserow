import { TestApp } from '@baserow/test/helpers/testApp'
import FunctionalGridViewFieldButtonField from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldButtonField'

describe('FunctionalGridViewFieldButtonField', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const field = {
    id: 2,
    type: 'button',
    label: 'Open',
    url_formula: {
      formula: "concat('https://example.com/', get('fields.field_1'))",
      mode: 'simple',
    },
  }

  const mountCell = async (props = {}) =>
    testApp.mount(FunctionalGridViewFieldButtonField, {
      propsData: {
        field,
        value: null,
        row: { id: 1, field_1: 'ada' },
        ...props,
      },
    })

  test('resolves the URL through the field store when allFieldsInTable is absent', async () => {
    testApp.store.commit('field/SET_ITEMS', [
      { id: 1, type: 'text', name: 'Slug' },
      field,
    ])
    const wrapper = await mountCell()
    const anchor = wrapper.find('a')
    expect(anchor.attributes('href')).toBe('https://example.com/ada')
    expect(anchor.text()).toBe('Open')
  })

  test('renders a disabled button when the store has no fields to resolve against', async () => {
    testApp.store.commit('field/SET_ITEMS', [])
    const wrapper = await mountCell()
    expect(wrapper.find('a').attributes('href')).toBeUndefined()
  })
})
