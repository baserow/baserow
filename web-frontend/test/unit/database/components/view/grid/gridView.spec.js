import GridView from '@baserow/modules/database/components/view/grid/GridView'
import GridViewFreezeHandle from '@baserow/modules/database/components/view/grid/GridViewFreezeHandle'

describe('GridView component', () => {
  const fields = [
    { id: 1, name: 'Primary', primary: true },
    { id: 2, name: 'Hidden', primary: false },
    { id: 3, name: 'Visible', primary: false },
  ]
  const fieldOptions = {
    1: { order: 0, hidden: true },
    2: { order: 1, hidden: true },
    3: { order: 2, hidden: false },
  }

  test('leftFields includes the primary field when it is hidden', () => {
    const leftFields = GridView.computed.leftFields.call({
      fields,
      fieldOptions,
      frozenColumnCount: 2,
      hasFrozenColumns: true,
    })

    expect(leftFields.map((field) => field.id)).toEqual([1, 3])
  })

  test('rightVisibleFields includes the primary field when frozen columns are disabled', () => {
    const rightVisibleFields = GridView.computed.rightVisibleFields.call({
      rightFields: fields,
      fieldOptions,
    })

    expect(rightVisibleFields.map((field) => field.id)).toEqual([1, 3])
  })

  test('hiddenFields excludes the primary field when it is hidden', () => {
    const hiddenFields = GridView.computed.hiddenFields.call({
      rightFields: fields,
      fieldOptions,
    })

    expect(hiddenFields.map((field) => field.id)).toEqual([2])
  })

  test('freeze handle sortedFields includes the primary field when it is hidden', () => {
    const sortedFields = GridViewFreezeHandle.computed.sortedFields.call({
      fields,
      fieldOptions,
    })

    expect(sortedFields.map((field) => field.id)).toEqual([1, 3])
  })
})
