import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldType from '@baserow/modules/database/components/view/grid/GridViewFieldType'
import { MAX_GROUP_BYS } from '@baserow/modules/database/constants'

describe('GridViewFieldType group by menu item', () => {
  let testApp = null
  let mockServer = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    store.$config = { public: { baserowRowPageSizeLimit: 200 } }
    mockServer = testApp.mockServer
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const primary = {
    id: 1,
    name: 'Name',
    order: 0,
    type: 'text',
    primary: true,
    text_default: '',
    _: { loading: false, type: { iconClass: 'iconoir-text', name: 'text' } },
  }

  const textField = {
    id: 2,
    name: 'Surname',
    order: 1,
    type: 'text',
    primary: false,
    text_default: '',
    _: { loading: false, type: { iconClass: 'iconoir-text', name: 'text' } },
  }

  const richTextField = {
    id: 3,
    name: 'Notes',
    order: 2,
    type: 'long_text',
    primary: false,
    long_text_enable_rich_text: true,
    _: {
      loading: false,
      type: { iconClass: 'iconoir-text', name: 'long_text' },
    },
  }

  const allFields = [textField, richTextField]

  const groupBy = (fieldId) => ({
    id: `gb-${fieldId}`,
    field: fieldId,
    order: 'ASC',
    type: 'default',
    width: 200,
    _: { loading: false },
  })

  const populateStore = async (groupBys = []) => {
    const table = mockServer.createTable()
    const { application } = await mockServer.createAppAndWorkspace(table)
    const view = mockServer.createGridView(application, table, { groupBys })
    const fields = mockServer.createFields(application, table, allFields)
    mockServer.createGridRows(view, fields, [])
    await store.dispatch('page/view/grid/fetchInitial', {
      gridId: 1,
      fields,
      primary,
    })
    await store.dispatch('view/fetchAll', { id: 1 })
    return { table, application, view }
  }

  const mountFieldType = async ({ table, application, view }, field) => {
    const wrapper = await testApp.mount(GridViewFieldType, {
      props: {
        database: application,
        table,
        view,
        field,
        readOnly: false,
        allFieldsInTable: allFields,
        storePrefix: 'page/',
      },
    })
    await wrapper.vm.$refs.context.toggle(wrapper.vm.$refs.contextLink)
    await wrapper.vm.$nextTick()
    return wrapper
  }

  const findGroupByItem = (wrapper) =>
    wrapper
      .findAll('.context__menu-item-link')
      .find((item) => item.find('.iconoir-book-stack').exists())

  test('shows "Group by this field" and creates a group by on click', async () => {
    const context = await populateStore([])
    const wrapper = await mountFieldType(context, textField)

    const item = findGroupByItem(wrapper)
    expect(item).toBeTruthy()
    expect(item.text()).toContain('gridViewFieldType.groupByField')
    expect(item.classes()).not.toContain('context__menu-item-link--active')
    expect(item.find('.context__menu-active-icon').exists()).toBe(false)

    const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue()
    await item.trigger('click')

    expect(dispatch).toHaveBeenCalledWith(
      'view/createGroupBy',
      expect.objectContaining({
        view: context.view,
        values: expect.objectContaining({ field: textField.id, order: 'ASC' }),
      })
    )
  })

  test('shows "Don\'t group by this field" and removes it on click', async () => {
    const context = await populateStore([groupBy(textField.id)])
    const wrapper = await mountFieldType(context, textField)

    const item = findGroupByItem(wrapper)
    expect(item).toBeTruthy()
    expect(item.text()).toContain('gridViewFieldType.ungroupByField')
    expect(item.classes()).not.toContain('context__menu-item-link--active')
    expect(item.find('.context__menu-active-icon').exists()).toBe(false)

    const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue()
    await item.trigger('click')

    expect(dispatch).toHaveBeenCalledWith(
      'view/deleteGroupBy',
      expect.objectContaining({
        view: context.view,
        groupBy: expect.objectContaining({ field: textField.id }),
      })
    )
  })

  test('is hidden for a field type that cannot be grouped by', async () => {
    const context = await populateStore([])
    const wrapper = await mountFieldType(context, richTextField)

    expect(findGroupByItem(wrapper)).toBeFalsy()
  })

  test('is hidden when the group by limit is reached and the field is not grouped', async () => {
    const groupBys = Array.from({ length: MAX_GROUP_BYS }, (_, i) =>
      groupBy(100 + i)
    )
    const context = await populateStore(groupBys)
    const wrapper = await mountFieldType(context, textField)

    expect(findGroupByItem(wrapper)).toBeFalsy()
  })
})
