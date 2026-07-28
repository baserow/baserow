import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldButtonField from '@baserow/modules/database/components/view/grid/fields/GridViewFieldButtonField'

describe('GridViewFieldButtonField', () => {
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
    testApp.mount(GridViewFieldButtonField, {
      propsData: {
        field,
        value: null,
        row: { id: 1, field_1: 'ada' },
        allFieldsInTable: [{ id: 1, type: 'text', name: 'Slug' }, field],
        selected: false,
        readOnly: true,
        storePrefix: 'page/',
        workspaceId: 1,
        ...props,
      },
    })

  test('renders an enabled link with the resolved URL', async () => {
    const wrapper = await mountCell()
    const anchor = wrapper.find('a')
    expect(anchor.attributes('href')).toBe('https://example.com/ada')
    expect(anchor.attributes('target')).toBe('_blank')
    expect(anchor.text()).toBe('Open')
  })

  test('falls back to the URL as typed when there is no label', async () => {
    // Not the percent-encoded href: the label is what the user built.
    const wrapper = await mountCell({
      field: { ...field, label: '' },
      row: { id: 1, field_1: 'Red Button' },
    })
    const anchor = wrapper.find('a')
    expect(anchor.attributes('href')).toBe('https://example.com/Red%20Button')
    expect(anchor.text()).toBe('https://example.com/Red Button')
  })

  test('falls back to a default label when there is no label and no URL', async () => {
    const wrapper = await mountCell({
      field: {
        ...field,
        label: '',
        url_formula: { formula: '', mode: 'simple' },
      },
    })
    // The test i18n stub returns the key rather than the translation.
    expect(wrapper.find('a').text()).toBe('buttonField.defaultLabel')
  })

  test('renders a disabled button when the URL does not resolve', async () => {
    // An empty url_formula never resolves (resolveButtonUrl short-circuits
    // to ''), unlike an empty field_1 which still yields a valid base URL
    // once concatenated with the literal prefix above.
    const wrapper = await mountCell({
      field: { ...field, url_formula: { formula: '', mode: 'simple' } },
    })
    expect(wrapper.find('a').attributes('href')).toBeUndefined()
  })

  test('renders a disabled button when the field has a broken formula error, even if the URL would otherwise resolve', async () => {
    const wrapper = await mountCell({
      field: {
        ...field,
        error: 'The formula references a field that no longer exists.',
      },
    })
    expect(wrapper.find('a').attributes('href')).toBeUndefined()
  })
})
