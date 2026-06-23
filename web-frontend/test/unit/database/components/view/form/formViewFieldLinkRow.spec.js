import { TestApp } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

import FormViewFieldLinkRow from '@baserow/modules/database/components/view/form/FormViewFieldLinkRow'
import FormViewFieldMultipleLinkRow from '@baserow/modules/database/components/view/form/FormViewFieldMultipleLinkRow'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import ViewService from '@baserow/modules/database/services/view'
import { LinkRowFieldType } from '@baserow/modules/database/fieldTypes'

vi.mock('@baserow/modules/database/services/view', () => ({
  default: vi.fn(),
}))

const mockLinkRowFieldLookup = (rows) => {
  const linkRowFieldLookup = vi
    .fn()
    .mockResolvedValue({ data: { results: rows, count: rows.length } })
  ViewService.mockReturnValue({ linkRowFieldLookup })
  return linkRowFieldLookup
}

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

  test('fetchPage returns the fetched results unchanged (pure pass-through)', async () => {
    const rows = [
      { id: 42, value: '' },
      { id: 43, value: 'Real name' },
    ]
    mockLinkRowFieldLookup(rows)
    const wrapper = await mountComponent({ value: [] })
    const { data } = await wrapper.vm.fetchPage(1, null)

    // The dropdown derives the label through valueName and hands the row back
    // on selection, so fetchPage must not mutate the results or keep a copy.
    expect(data.results).toEqual(rows)
    expect(wrapper.vm.rowLookup).toBeUndefined()
  })

  test('rowDisplayName falls back to the unnamed label for empty primaries', async () => {
    const wrapper = await mountComponent({ value: [] })
    expect(wrapper.vm.rowDisplayName({ id: 42, value: '' })).toBe(
      'functionnalGridViewFieldLinkRow.unnamed'
    )
    expect(wrapper.vm.rowDisplayName({ id: 42, value: 'Name' })).toBe('Name')
    // Placeholder slots (no real id) keep their empty value.
    expect(wrapper.vm.rowDisplayName({ id: false, value: '' })).toBe('')
  })

  test('updateValue stores the original empty value, not the fallback label', async () => {
    const wrapper = await mountComponent({ value: [] })

    wrapper.vm.updateValue({
      value: 42,
      displayName: 'functionnalGridViewFieldLinkRow.unnamed',
      item: { id: 42, value: '' },
    })

    const emitted = wrapper.emitted('update')
    expect(emitted).toBeTruthy()
    expect(emitted[emitted.length - 1][0]).toEqual([{ id: 42, value: '' }])
  })

  test('updateValue falls back to displayName when the item is not resolved', async () => {
    const wrapper = await mountComponent({ value: [] })
    // No item (e.g. a pre-existing selection not in the current results).
    wrapper.vm.updateValue({ value: 99, displayName: 'pre-existing' })

    const emitted = wrapper.emitted('update')
    expect(emitted[emitted.length - 1][0]).toEqual([
      { id: 99, value: 'pre-existing' },
    ])
  })

  test('updateValue with null emits an empty selection', async () => {
    const wrapper = await mountComponent({ value: [{ id: 42, value: '' }] })
    wrapper.vm.updateValue({ value: null, displayName: '' })

    const emitted = wrapper.emitted('update')
    expect(emitted[emitted.length - 1][0]).toEqual([])
  })

  test('emitted value of an unnamed row is not empty by LinkRowFieldType', async () => {
    const wrapper = await mountComponent({ value: [] })

    wrapper.vm.updateValue({
      value: 42,
      displayName: 'functionnalGridViewFieldLinkRow.unnamed',
      item: { id: 42, value: '' },
    })

    const emitted = wrapper.emitted('update')
    const newValue = emitted[emitted.length - 1][0]

    // A picked row is a real selection, so isEmpty is false even with an empty
    // primary, keeping a "show when not empty" condition's field visible.
    const fieldType = new LinkRowFieldType({ app: testApp.store.$app })
    expect(fieldType.isEmpty(linkRowField, newValue)).toBe(false)
  })

  test('required + picked unnamed row passes validation (no false require error)', async () => {
    const wrapper = await mountComponent({
      value: [{ id: 42, value: '' }],
      required: true,
    })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBeNull()
  })

  test('required + empty selection fails validation', async () => {
    const wrapper = await mountComponent({ value: [], required: true })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBe(
      'error.requiredField'
    )
  })

  test('required + named row passes validation', async () => {
    const wrapper = await mountComponent({
      value: [{ id: 42, value: 'Hello' }],
      required: true,
    })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBeNull()
  })

  test('non-required + empty selection passes validation', async () => {
    const wrapper = await mountComponent({ value: [], required: false })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBeNull()
  })

  test('does not render the empty option at the top of the dropdown', async () => {
    const wrapper = await mountComponent({ value: [] })
    // The blank entry that PaginatedDropdown adds by default must be suppressed,
    // otherwise an empty option shows up at the top of the link-row dropdown.
    expect(wrapper.findComponent(PaginatedDropdown).props('addEmptyItem')).toBe(
      false
    )
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

  test('fetchPage returns the fetched results unchanged (pure pass-through)', async () => {
    const rows = [
      { id: 42, value: '' },
      { id: 43, value: 'Real name' },
    ]
    mockLinkRowFieldLookup(rows)
    const wrapper = await mountComponent({ value: [{ id: false, value: '' }] })
    const { data } = await wrapper.vm.fetchPage(1, null)

    expect(data.results).toEqual(rows)
    expect(wrapper.vm.rowLookup).toBeUndefined()
  })

  test('rowDisplayName falls back to the unnamed label for empty primaries', async () => {
    const wrapper = await mountComponent({ value: [{ id: false, value: '' }] })
    expect(wrapper.vm.rowDisplayName({ id: 42, value: '' })).toBe(
      'functionnalGridViewFieldLinkRow.unnamed'
    )
    expect(wrapper.vm.rowDisplayName({ id: 42, value: 'Name' })).toBe('Name')
    expect(wrapper.vm.rowDisplayName({ id: false, value: '' })).toBe('')
  })

  test('updateValue stores the original empty value, not the fallback label', async () => {
    const wrapper = await mountComponent({ value: [{ id: false, value: '' }] })

    wrapper.vm.updateValue(
      {
        value: 42,
        displayName: 'functionnalGridViewFieldLinkRow.unnamed',
        item: { id: 42, value: '' },
      },
      0
    )

    const emitted = wrapper.emitted('update')
    expect(emitted).toBeTruthy()
    expect(emitted[emitted.length - 1][0]).toEqual([{ id: 42, value: '' }])
  })

  test('updateValue falls back to displayName when the item is not resolved', async () => {
    const wrapper = await mountComponent({ value: [{ id: false, value: '' }] })
    wrapper.vm.updateValue({ value: 99, displayName: 'pre-existing' }, 0)

    const emitted = wrapper.emitted('update')
    expect(emitted[emitted.length - 1][0]).toEqual([
      { id: 99, value: 'pre-existing' },
    ])
  })

  test('updateValue with null clears the slot', async () => {
    const wrapper = await mountComponent({ value: [{ id: 42, value: '' }] })
    wrapper.vm.updateValue({ value: null, displayName: '' }, 0)

    const emitted = wrapper.emitted('update')
    expect(emitted[emitted.length - 1][0]).toEqual([{ id: null, value: '' }])
  })

  test('emitted value of an unnamed row is not empty by LinkRowFieldType', async () => {
    const wrapper = await mountComponent({ value: [{ id: false, value: '' }] })

    wrapper.vm.updateValue(
      {
        value: 42,
        displayName: 'functionnalGridViewFieldLinkRow.unnamed',
        item: { id: 42, value: '' },
      },
      0
    )

    const emitted = wrapper.emitted('update')
    const newValue = emitted[emitted.length - 1][0]

    // A picked row is a real selection, so isEmpty is false even with an empty
    // primary, matching the backend's many-to-many empty semantics.
    const fieldType = new LinkRowFieldType({ app: testApp.store.$app })
    expect(fieldType.isEmpty(linkRowField, newValue)).toBe(false)
  })

  test('required + every slot has a real id passes validation (no false require error)', async () => {
    const wrapper = await mountComponent({
      value: [{ id: 42, value: '' }],
      required: true,
    })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBeNull()
  })

  test('required + a placeholder slot {id:false} fails validation', async () => {
    const wrapper = await mountComponent({
      value: [
        { id: 42, value: '' },
        { id: false, value: '' },
      ],
      required: true,
    })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBe(
      'error.requiredField'
    )
  })

  test('required + empty array fails validation', async () => {
    const wrapper = await mountComponent({ value: [], required: true })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBe(
      'error.requiredField'
    )
  })

  test('non-required + placeholder slot still fails validation', async () => {
    const wrapper = await mountComponent({
      value: [{ id: false, value: '' }],
      required: false,
    })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBe(
      'error.requiredField'
    )
  })

  test('non-required + empty array passes validation', async () => {
    const wrapper = await mountComponent({ value: [], required: false })
    expect(wrapper.vm.getValidationError(wrapper.vm.value)).toBeNull()
  })

  test('does not render the empty option in any slot dropdown', async () => {
    const wrapper = await mountComponent({ value: [{ id: 42, value: '' }] })
    // Each slot's PaginatedDropdown must suppress the default blank entry; slots
    // are cleared with the bin button, not an empty option in the list.
    expect(wrapper.findComponent(PaginatedDropdown).props('addEmptyItem')).toBe(
      false
    )
  })
})
