import { vi } from 'vitest'
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

  const mountCell = async (props = {}) => {
    const wrapper = await testApp.mount(GridViewFieldButtonField, {
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
    // Dispatch goes through the real $client instance shared by the test
    // app, so replace .post with a fresh mock per mount instead of hitting
    // the network mock adapter.
    wrapper.vm.$client.post = vi.fn().mockResolvedValue({ data: {} })
    return wrapper
  }

  test('renders an enabled link with the resolved URL', async () => {
    const wrapper = await mountCell()
    const anchor = wrapper.find('a')
    expect(anchor.attributes('href')).toBe('https://example.com/ada')
    expect(anchor.attributes('target')).toBe('_blank')
    expect(anchor.text()).toBe('Open')
  })

  test('percent-encodes the whitespace in the href but not in the label', async () => {
    const wrapper = await mountCell({
      row: { id: 1, field_1: 'Red Button' },
    })
    const anchor = wrapper.find('a')
    expect(anchor.attributes('href')).toBe('https://example.com/Red%20Button')
    expect(anchor.text()).toBe('Open')
  })

  test('renders a disabled button with the label when the URL does not resolve', async () => {
    // An empty url_formula never resolves (resolveButtonUrl short-circuits
    // to ''), unlike an empty field_1 which still yields a valid base URL
    // once concatenated with the literal prefix above.
    const wrapper = await mountCell({
      field: { ...field, url_formula: { formula: '', mode: 'simple' } },
    })
    const anchor = wrapper.find('a')
    expect(anchor.attributes('href')).toBeUndefined()
    expect(anchor.text()).toBe('Open')
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

  test('a field with actions renders a button and dispatches on click', async () => {
    const fieldWithActions = { ...field, has_workflow_actions: true }
    const wrapper = await mountCell({ field: fieldWithActions })

    expect(wrapper.find('button').exists()).toBe(true)

    await wrapper.find('button').trigger('click')

    expect(wrapper.vm.$client.post).toHaveBeenCalledWith(
      `database/field/${fieldWithActions.id}/workflow_actions/dispatch/`,
      { row_id: 1 }
    )
  })

  test('a field with no actions still renders a link', async () => {
    const wrapper = await mountCell({
      field: { ...field, has_workflow_actions: false },
    })

    expect(wrapper.find('a').exists()).toBe(true)
    expect(wrapper.find('button').exists()).toBe(false)
  })

  test('a failed dispatch leaves the cell clickable', async () => {
    const fieldWithActions = { ...field, has_workflow_actions: true }
    const wrapper = await mountCell({ field: fieldWithActions })
    wrapper.vm.$client.post.mockRejectedValueOnce(new Error('nope'))

    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.dispatching).toBe(false)
  })
})
