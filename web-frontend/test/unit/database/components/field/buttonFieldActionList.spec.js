import { readFileSync } from 'fs'
import { resolve } from 'path'
import { TestApp } from '@baserow/test/helpers/testApp'
import ButtonFieldActionList from '@baserow/modules/database/components/field/ButtonFieldActionList'

// Read rather than imported: the i18n loader turns an imported locale file
// into compiled message ASTs, which the copy below can't be read off of.
const en = JSON.parse(
  readFileSync(
    resolve(process.cwd(), 'modules/database/locales/en.json'),
    'utf8'
  )
)

describe('ButtonFieldActionList', () => {
  let testApp = null

  // Mounting a row also mounts its form, which emits its own defaults once.
  // Assert on what the action under test emitted, not on that.
  const lastEmitted = (wrapper) => {
    const emitted = wrapper.emitted('input')
    return emitted[emitted.length - 1][0]
  }
  const emittedCount = (wrapper) => (wrapper.emitted('input') ?? []).length

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountList = async (value = []) =>
    testApp.mount(ButtonFieldActionList, {
      propsData: {
        value,
        database: { id: 1, workspace: { id: 1 } },
      },
    })

  test('adding an action emits a longer list and calls no api', async () => {
    const wrapper = await mountList([])

    await wrapper.vm.addAction('create_row')

    const emitted = wrapper.emitted('input')
    expect(emitted).toHaveLength(1)
    expect(emitted[0][0]).toHaveLength(1)
    expect(emitted[0][0][0].type).toBe('create_row')
    expect(emitted[0][0][0].id).toBeUndefined()
  })

  test('add action appends a row with no type yet', async () => {
    // The type is chosen from the row's own dropdown afterwards, so the row
    // starts out empty rather than guessing a type for the user.
    const wrapper = await mountList([])

    await wrapper.vm.addAction()

    expect(wrapper.emitted('input')[0][0]).toEqual([{ type: null }])
  })

  test('the row dropdown offers every registered type, in order', async () => {
    const wrapper = await mountList([{ type: null }])

    const items = wrapper
      .findComponent({ name: 'Dropdown' })
      .findAllComponents({ name: 'DropdownItem' })

    expect(items.map((item) => item.props('value'))).toEqual([
      'open_url',
      'create_row',
      'update_row',
      'delete_row',
    ])
    // `$t` returns the key in the test env, so the name is checked against
    // the key the type uses and the copy itself is pinned separately.
    expect(items[0].props('name')).toBe('databaseWorkflowActionType.openUrl')
    expect(en.databaseWorkflowActionType.openUrl).toBe('Open URL')
    expect(items[0].props('icon')).toBe('iconoir-link')
  })

  test('a row with no type shows the placeholder and no form', async () => {
    const wrapper = await mountList([{ type: null }])

    expect(wrapper.findComponent({ name: 'Dropdown' }).props('value')).toBe(
      null
    )
    expect(
      wrapper.findComponent({ name: 'Dropdown' }).props('placeholder')
    ).toBe('buttonFieldActionList.chooseAction')
    expect(en.buttonFieldActionList.chooseAction).toBe('Choose action...')
    expect(
      wrapper
        .findComponent({ name: 'DatabaseWorkflowActionWithService' })
        .exists()
    ).toBe(false)
    expect(
      wrapper.findComponent({ name: 'OpenUrlWorkflowActionForm' }).exists()
    ).toBe(false)
  })

  test('each row renders the form of its own type', async () => {
    // Regression test: the list used to render the service backed form for
    // every row, which threw on `open_url` because that type has no service.
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: {} },
      { id: 2, type: 'open_url', url: { formula: '', mode: 'simple' } },
    ])

    expect(
      wrapper.findAllComponents({ name: 'DatabaseWorkflowActionWithService' })
    ).toHaveLength(1)
    expect(
      wrapper.findAllComponents({ name: 'OpenUrlWorkflowActionForm' })
    ).toHaveLength(1)
  })

  test('changing between two service types remounts the form', async () => {
    // `create_row` and `update_row` resolve to the same form component and
    // the same `serviceType.formComponent`, and the row's own key does not
    // change on a type swap. Without a type derived key Vue reuses the
    // instance, so the inner form keeps the values it seeded from the old
    // config and the user still sees the old table selected.
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: { table_id: 3 } },
    ])
    const before = wrapper.findComponent({
      name: 'DatabaseWorkflowActionWithService',
    }).vm

    await wrapper.setProps({
      value: [{ id: 1, type: 'update_row', service: {} }],
    })

    const after = wrapper.findComponent({
      name: 'DatabaseWorkflowActionWithService',
    }).vm
    expect(after).not.toBe(before)
  })

  test('changing a row type keeps its id and drops the old config', async () => {
    // The old type's config means nothing to the new one, and the server
    // deletes and recreates the action rather than converting it.
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: { table_id: 3 } },
      { id: 2, type: 'delete_row', service: {} },
    ])

    await wrapper.vm.onActionTypeChanged(0, 'open_url')

    expect(lastEmitted(wrapper)).toEqual([
      { id: 1, type: 'open_url' },
      { id: 2, type: 'delete_row', service: {} },
    ])
  })

  test('choosing a type on a new row seeds that type defaults', async () => {
    const wrapper = await mountList([{ type: null }])

    await wrapper.vm.onActionTypeChanged(0, 'create_row')

    expect(wrapper.emitted('input')[0][0]).toEqual([
      { type: 'create_row', service: {} },
    ])
  })

  test('an unchanged type emits nothing', async () => {
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: { table_id: 3 } },
    ])
    const before = emittedCount(wrapper)

    await wrapper.vm.onActionTypeChanged(0, 'create_row')

    expect(emittedCount(wrapper)).toBe(before)
  })

  test('an open url form edit is buffered onto the action', async () => {
    // `open_url` has no service: its config lives on the action itself, so
    // the list has to accept whatever keys the type's form emits.
    const wrapper = await mountList([{ id: 1, type: 'open_url' }])

    await wrapper.vm.onActionValuesChanged(0, {
      url: { formula: "'x'", mode: 'simple' },
      target: 'blank',
    })

    expect(lastEmitted(wrapper)).toEqual([
      {
        id: 1,
        type: 'open_url',
        url: { formula: "'x'", mode: 'simple' },
        target: 'blank',
      },
    ])
  })

  test('removing an action emits a shorter list', async () => {
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: {} },
      { id: 2, type: 'delete_row', service: {} },
    ])

    await wrapper.vm.removeAction(0)

    const emitted = wrapper.emitted('input')
    expect(emitted[0][0].map((a) => a.id)).toEqual([2])
  })

  test('reordering emits the new order', async () => {
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: {} },
      { id: 2, type: 'delete_row', service: {} },
    ])

    await wrapper.vm.orderActions([
      { id: 2, type: 'delete_row', service: {} },
      { id: 1, type: 'create_row', service: {} },
    ])

    const emitted = wrapper.emitted('input')
    expect(emitted[0][0].map((a) => a.id)).toEqual([2, 1])
  })

  test('onSortableUpdate resolves ids correctly when a saved action id collides with an unsaved action index', async () => {
    // The saved action's real id (1) is numerically identical to the unsaved
    // action's fallback index (1). The sortable id namespacing must keep
    // these two apart, or the id-to-action lookup collides and drops one
    // action as undefined.
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: {} },
      { type: 'delete_row', service: {} },
    ])

    await wrapper.vm.onSortableUpdate(['new-1', 1])

    const emitted = wrapper.emitted('input')
    const [reordered] = emitted[emitted.length - 1]
    expect(reordered).toHaveLength(2)
    expect(reordered.every((a) => a !== undefined)).toBe(true)
    expect(reordered[0].type).toBe('delete_row')
    expect(reordered[0].id).toBeUndefined()
    expect(reordered[1].type).toBe('create_row')
    expect(reordered[1].id).toBe(1)
  })

  test('it renders one form per action', async () => {
    const wrapper = await mountList([
      { id: 1, type: 'create_row', service: {} },
      { id: 2, type: 'delete_row', service: {} },
    ])

    expect(
      wrapper.findAllComponents({ name: 'DatabaseWorkflowActionWithService' })
    ).toHaveLength(2)
  })
})
