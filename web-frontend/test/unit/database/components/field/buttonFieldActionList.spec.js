import { TestApp } from '@baserow/test/helpers/testApp'
import ButtonFieldActionList from '@baserow/modules/database/components/field/ButtonFieldActionList'

describe('ButtonFieldActionList', () => {
  let testApp = null

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
