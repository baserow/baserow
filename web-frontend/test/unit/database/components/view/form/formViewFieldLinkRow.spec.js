import { TestApp } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

import FormViewFieldLinkRow from '@baserow/modules/database/components/view/form/FormViewFieldLinkRow'
import FormViewFieldMultipleLinkRow from '@baserow/modules/database/components/view/form/FormViewFieldMultipleLinkRow'

const linkRowField = {
  id: 1,
  table_id: 196,
  name: 'Related',
  order: 0,
  type: 'link_row',
  primary: false,
  link_row_table_id: 197,
  link_row_related_field_id: 99,
  link_row_limit_selection_view_id: null,
  link_row_multiple_relationships: true,
  _: { loading: false },
}

const baseProps = {
  slug: 'form-slug',
  field: linkRowField,
  readOnly: false,
  required: false,
  workspaceId: 1,
}

describe('FormViewFieldLinkRow', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
    vi.restoreAllMocks()
  })

  const mountComponent = (props) =>
    testApp.mount(FormViewFieldLinkRow, {
      propsData: { ...baseProps, lazyLoad: true, ...props },
    })

  test('initialDisplayName falls back to unnamed-row label when value is empty', async () => {
    const wrapper = await mountComponent({
      value: [{ id: 42, value: '' }],
    })
    await flushPromises()
    expect(wrapper.text()).toContain('functionnalGridViewFieldLinkRow.unnamed')
  })

  test('initialDisplayName uses the primary value when present', async () => {
    const wrapper = await mountComponent({
      value: [{ id: 42, value: 'Hello world' }],
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Hello world')
  })
})

describe('FormViewFieldMultipleLinkRow', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
    vi.restoreAllMocks()
  })

  const mountComponent = (props) =>
    testApp.mount(FormViewFieldMultipleLinkRow, {
      propsData: { ...baseProps, lazyLoad: true, ...props },
    })

  test('renders unnamed-row fallback for stored empty values', async () => {
    const wrapper = await mountComponent({
      value: [{ id: 42, value: '' }],
    })
    await flushPromises()
    expect(wrapper.text()).toContain('functionnalGridViewFieldLinkRow.unnamed')
  })

  test('uses the primary value when present', async () => {
    const wrapper = await mountComponent({
      value: [{ id: 42, value: 'Hello world' }],
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Hello world')
  })

  test('does not render fallback for a fresh empty slot (id=false)', async () => {
    const wrapper = await mountComponent({
      value: [{ id: false, value: '' }],
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain(
      'functionnalGridViewFieldLinkRow.unnamed'
    )
  })
})
