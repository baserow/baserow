import { TestApp } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

import FieldLinkRowSubForm from '@baserow/modules/database/components/field/FieldLinkRowSubForm'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'
import ViewService from '@baserow/modules/database/services/view'

vi.mock('@baserow/modules/database/services/view', () => ({
  default: vi.fn(),
}))

const DATABASE_ID = 100
const LINKED_TABLE_ID = 2
const LIMIT_VIEW_ID = 10

const collaborativeGridView = {
  id: LIMIT_VIEW_ID,
  name: 'Active Projects',
  type: 'grid',
  order: 1,
  ownership_type: 'collaborative',
}

const mockFetchAll = (views) => {
  const fetchAll = vi.fn().mockResolvedValue({ data: views })
  ViewService.mockReturnValue({ fetchAll })
  return fetchAll
}

describe('FieldLinkRowSubForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
    vi.restoreAllMocks()
  })

  const database = { id: DATABASE_ID, workspace: { id: 1 } }
  const table = { id: 1, name: 'Customers', database_id: DATABASE_ID }

  const baseProps = {
    table,
    database,
    view: {},
    allFieldsInTable: [],
    fieldType: 'link_row',
  }

  const mountComponent = async (defaultValues) => {
    // The component reads the linkable tables from the application store.
    await testApp.store.dispatch('application/forceCreate', {
      id: DATABASE_ID,
      type: 'database',
      workspace: { id: 1 },
      tables: [
        { id: LINKED_TABLE_ID, name: 'Projects', database_id: DATABASE_ID },
      ],
    })
    const wrapper = await testApp.mount(FieldLinkRowSubForm, {
      propsData: { ...baseProps, defaultValues },
    })
    await flushPromises()
    return wrapper
  }

  const renderedItemValues = (wrapper) =>
    wrapper.findAllComponents(DropdownItem).map((item) => item.props('value'))

  const selectedDropdownTexts = (wrapper) =>
    wrapper.findAll('.dropdown__selected-text').map((el) => el.text())

  test('opening a field already limited to a view loads and shows that view', async () => {
    const fetchAll = mockFetchAll([collaborativeGridView])
    const wrapper = await mountComponent({
      link_row_table_id: LINKED_TABLE_ID,
      link_row_limit_selection_view_id: LIMIT_VIEW_ID,
      link_row_multiple_relationships: true,
    })

    // The user-visible symptom: the dropdown shows the saved view's name as
    // its selected value, instead of falling back to the "Make a choice"
    // placeholder (the "my view selection is gone" bug).
    expect(selectedDropdownTexts(wrapper)).toContain('Active Projects')
    expect(wrapper.text()).not.toContain('Make a choice')
    // The previously selected view is listed as an option, so the dropdown
    // is not the empty "No items available" list.
    expect(renderedItemValues(wrapper)).toContain(LIMIT_VIEW_ID)
    // ...because the linked table's views are fetched on mount.
    expect(fetchAll).toHaveBeenCalled()
    expect(fetchAll.mock.calls[0][0]).toBe(LINKED_TABLE_ID)
  })

  test('opening a field without a limit view does not fetch views on mount', async () => {
    const fetchAll = mockFetchAll([collaborativeGridView])
    const wrapper = await mountComponent({
      link_row_table_id: LINKED_TABLE_ID,
      link_row_limit_selection_view_id: null,
      link_row_multiple_relationships: true,
    })

    // Nothing to restore, so the views dropdown stays hidden and unfetched.
    expect(fetchAll).not.toHaveBeenCalled()
    expect(renderedItemValues(wrapper)).not.toContain(LIMIT_VIEW_ID)
  })
})
