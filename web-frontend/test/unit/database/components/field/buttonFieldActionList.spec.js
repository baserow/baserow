import { vi } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { TestApp } from '@baserow/test/helpers/testApp'
import ButtonFieldActionList from '@baserow/modules/database/components/field/ButtonFieldActionList'
import ButtonFieldActionForm from '@baserow/modules/database/components/field/ButtonFieldActionForm'
import { CLIENT_ID_KEY } from '@baserow/modules/database/utils/workflowActionReconciliation'

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

    await wrapper.vm.addAction('local_baserow_create_row')

    const emitted = wrapper.emitted('input')
    expect(emitted).toHaveLength(1)
    expect(emitted[0][0]).toHaveLength(1)
    expect(emitted[0][0][0].type).toBe('local_baserow_create_row')
    expect(emitted[0][0][0].id).toBeUndefined()
  })

  test('add action appends a row with no type yet', async () => {
    // The type is chosen from the row's own dropdown afterwards, so the row
    // starts out empty rather than guessing a type for the user.
    const wrapper = await mountList([])

    await wrapper.vm.addAction()

    expect(wrapper.emitted('input')[0][0]).toEqual([
      { [CLIENT_ID_KEY]: expect.any(String), type: null },
    ])
  })

  test('the row dropdown offers every registered type, in order', async () => {
    const wrapper = await mountList([{ type: null }])

    const items = wrapper
      .findComponent({ name: 'Dropdown' })
      .findAllComponents({ name: 'DropdownItem' })

    expect(items.map((item) => item.props('value'))).toEqual([
      'open_url',
      'local_baserow_create_row',
      'local_baserow_update_row',
      'local_baserow_delete_row',
      'http_request',
      'smtp_email',
    ])
    // `$t` returns the key in the test env, so the name is checked against
    // the key the type uses and the copy itself is pinned separately.
    expect(items[0].props('name')).toBe('databaseWorkflowActionType.openUrl')
    expect(en.databaseWorkflowActionType.openUrl).toBe('Open URL')
    expect(items[0].props('icon')).toBe('iconoir-link')
  })

  test('a type this instance cannot run is offered but not choosable', async () => {
    // Otherwise the only thing saying so is the refusal on save.
    testApp.store.commit('settings/SET_SETTINGS', {
      instance_smtp: { available: false, unavailable_reason: 'no_server' },
    })
    const wrapper = await mountList([{ type: null }])

    const items = wrapper
      .findComponent({ name: 'Dropdown' })
      .findAllComponents({ name: 'DropdownItem' })
    const email = items.find((item) => item.props('value') === 'smtp_email')

    expect(email.props('disabled')).toBe(true)
    expect(email.props('description')).toBe(
      'databaseWorkflowActionType.noInstanceSmtp'
    )
    // Every other type is left alone.
    expect(items[0].props('disabled')).toBe(false)

    testApp.store.commit('settings/SET_SETTINGS', {})
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
    // The list used to render the service backed form for every row, which
    // threw on `open_url` because that type has no service.
    const wrapper = await mountList([
      { id: 1, type: 'local_baserow_create_row', service: {} },
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
    // `create_row` and `update_row` share a form component, so without a type
    // derived key Vue reuses the instance and keeps the old table selected.
    const wrapper = await mountList([
      { id: 1, type: 'local_baserow_create_row', service: { table_id: 3 } },
    ])
    const before = wrapper.findComponent({
      name: 'DatabaseWorkflowActionWithService',
    }).vm

    await wrapper.setProps({
      value: [{ id: 1, type: 'local_baserow_update_row', service: {} }],
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
      { id: 1, type: 'local_baserow_create_row', service: { table_id: 3 } },
      { id: 2, type: 'local_baserow_delete_row', service: {} },
    ])

    await wrapper.vm.onActionTypeChanged(0, 'open_url')

    expect(lastEmitted(wrapper)).toEqual([
      { id: 1, [CLIENT_ID_KEY]: expect.any(String), type: 'open_url' },
      { id: 2, type: 'local_baserow_delete_row', service: {} },
    ])
  })

  test('choosing a type on a new row seeds that type defaults', async () => {
    const wrapper = await mountList([{ type: null }])

    await wrapper.vm.onActionTypeChanged(0, 'local_baserow_create_row')

    expect(wrapper.emitted('input')[0][0]).toEqual([
      {
        [CLIENT_ID_KEY]: expect.any(String),
        type: 'local_baserow_create_row',
        service: {},
      },
    ])
  })

  test('an unchanged type emits nothing', async () => {
    const wrapper = await mountList([
      { id: 1, type: 'local_baserow_create_row', service: { table_id: 3 } },
    ])
    const before = emittedCount(wrapper)

    await wrapper.vm.onActionTypeChanged(0, 'local_baserow_create_row')

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
      { id: 1, type: 'local_baserow_create_row', service: {} },
      { id: 2, type: 'local_baserow_delete_row', service: {} },
    ])

    await wrapper.vm.removeAction(0)

    const emitted = wrapper.emitted('input')
    expect(emitted[0][0].map((a) => a.id)).toEqual([2])
  })

  test('reordering emits the new order', async () => {
    const wrapper = await mountList([
      { id: 1, type: 'local_baserow_create_row', service: {} },
      { id: 2, type: 'local_baserow_delete_row', service: {} },
    ])

    await wrapper.vm.orderActions([
      { id: 2, type: 'local_baserow_delete_row', service: {} },
      { id: 1, type: 'local_baserow_create_row', service: {} },
    ])

    const emitted = wrapper.emitted('input')
    expect(emitted[0][0].map((a) => a.id)).toEqual([2, 1])
  })

  test('onSortableUpdate resolves a saved action and an unsaved one alike', async () => {
    // The unsaved action is identified by its client id rather than by where
    // it sits, so no saved id can be taken for an unsaved action's place.
    const wrapper = await mountList([
      { id: 1, type: 'local_baserow_create_row', service: {} },
      {
        [CLIENT_ID_KEY]: 'client-1',
        type: 'local_baserow_delete_row',
        service: {},
      },
    ])

    await wrapper.vm.onSortableUpdate(['client-1', 1])

    const emitted = wrapper.emitted('input')
    const [reordered] = emitted[emitted.length - 1]
    expect(reordered).toHaveLength(2)
    expect(reordered.every((a) => a !== undefined)).toBe(true)
    expect(reordered[0].type).toBe('local_baserow_delete_row')
    expect(reordered[0].id).toBeUndefined()
    expect(reordered[1].type).toBe('local_baserow_create_row')
    expect(reordered[1].id).toBe(1)
  })

  test('deleting an unsaved action leaves the one below as its own row', async () => {
    // Two unsaved actions of the same type render the same form, so if the
    // survivor takes over the deleted row Vue keeps that row's form state and
    // shows the deleted action's configuration.
    const wrapper = await mountList([
      { [CLIENT_ID_KEY]: 'client-1', type: 'open_url' },
      { [CLIENT_ID_KEY]: 'client-2', type: 'open_url' },
    ])

    const rowsBefore = wrapper.findAll('.button-field-action-list__item')
    const survivorBefore = rowsBefore[1].element
    const deletedBefore = rowsBefore[0].element

    await wrapper.setProps({
      value: [{ [CLIENT_ID_KEY]: 'client-2', type: 'open_url' }],
    })

    const rowsAfter = wrapper.findAll('.button-field-action-list__item')
    expect(rowsAfter).toHaveLength(1)
    expect(rowsAfter[0].element).toBe(survivorBefore)
    expect(rowsAfter[0].element).not.toBe(deletedBefore)
  })

  test('the sortable items have no non-sortable siblings', async () => {
    // The directive builds the new order from every element child of the
    // dragged item's parent, so a non-action sibling arrives with no id.
    const wrapper = await mountList([
      { id: 1, type: 'open_url' },
      { id: 2, type: 'open_url' },
    ])

    const items = wrapper.findAll('.button-field-action-list__item')
    expect(items).toHaveLength(2)

    const siblings = [...items[0].element.parentElement.children]
    expect(siblings).toHaveLength(2)
    expect(
      siblings.every((el) =>
        el.classList.contains('button-field-action-list__item')
      )
    ).toBe(true)
  })

  test('an unrecognised sortable id never puts undefined into the list', async () => {
    // An `undefined` id is exactly what the directive passes for a sibling
    // that carries no sortable id.
    const wrapper = await mountList([
      { id: 1, type: 'open_url' },
      { id: 2, type: 'open_url' },
    ])

    await wrapper.vm.onSortableUpdate([2, undefined, 1])

    const emitted = wrapper.emitted('input')
    const [reordered] = emitted[emitted.length - 1]
    expect(reordered.every((action) => action !== undefined)).toBe(true)
    expect(reordered.map((action) => action.id)).toEqual([2, 1])
  })

  test('it renders one form per action', async () => {
    const wrapper = await mountList([
      { id: 1, type: 'local_baserow_create_row', service: {} },
      { id: 2, type: 'local_baserow_delete_row', service: {} },
    ])

    expect(
      wrapper.findAllComponents({ name: 'DatabaseWorkflowActionWithService' })
    ).toHaveLength(2)
  })

  describe('misconfiguration', () => {
    const CREATE = (over = {}) => ({
      id: 1,
      type: 'local_baserow_create_row',
      service: { table_id: 7 },
      ...over,
    })
    const OPEN_URL = (over = {}) => ({
      id: 2,
      type: 'open_url',
      url: { formula: "'https://x.test'", mode: 'simple' },
      target: 'self',
      ...over,
    })

    const errors = (wrapper) =>
      wrapper.findAll('[data-action-error]').map((node) => node.text())

    test('a fully configured list is not marked', async () => {
      const wrapper = await mountList([CREATE(), OPEN_URL()])

      expect(errors(wrapper)).toEqual([])
      expect(wrapper.text()).not.toContain(
        'buttonFieldActionList.misconfigured'
      )
    })

    test('an action with no type chosen is not marked', async () => {
      // Half configured is a normal state while editing.
      const wrapper = await mountList([{ [CLIENT_ID_KEY]: 'a', type: null }])

      expect(errors(wrapper)).toEqual([])
    })

    test('an action with no table is marked', async () => {
      const wrapper = await mountList([CREATE({ service: {} })])

      expect(errors(wrapper)).toEqual(['serviceType.errorNoTableSelected'])
      expect(wrapper.text()).toContain('buttonFieldActionList.misconfigured')
      // The copy the key resolves to, so a rename of either is caught.
      expect(en.buttonFieldActionList.misconfigured).toBe(
        'At least one action is misconfigured'
      )
    })

    test('a url action with no url is marked', async () => {
      const wrapper = await mountList([
        OPEN_URL({ url: { formula: '', mode: 'simple' } }),
      ])

      expect(errors(wrapper)).toEqual(['databaseWorkflowActionType.noUrl'])
    })

    test('a reference to an earlier action is fine', async () => {
      const wrapper = await mountList([
        CREATE(),
        OPEN_URL({
          url: { formula: "get('previous_action.1.id')", mode: 'simple' },
        }),
      ])

      expect(errors(wrapper)).toEqual([])
    })

    test('a reference to an action that no longer precedes it is marked', async () => {
      // The same two actions, dragged the other way round.
      const wrapper = await mountList([
        OPEN_URL({
          url: { formula: "get('previous_action.1.id')", mode: 'simple' },
        }),
        CREATE(),
      ])

      expect(errors(wrapper)).toEqual([
        'databaseWorkflowActionType.staleReference',
      ])
    })

    test('dragging it back clears the mark, with nothing retyped', async () => {
      const chained = OPEN_URL({
        url: { formula: "get('previous_action.1.id')", mode: 'simple' },
      })
      const wrapper = await mountList([chained, CREATE()])
      expect(errors(wrapper)).toHaveLength(1)

      await wrapper.setProps({ value: [CREATE(), chained] })

      expect(errors(wrapper)).toEqual([])
      // The reference is kept rather than cleared, which is what makes the
      // reorder reversible at all.
      expect(chained.url.formula).toBe("get('previous_action.1.id')")
    })

    test('a reference to a deleted action is marked', async () => {
      const wrapper = await mountList([
        OPEN_URL({
          url: { formula: "get('previous_action.99.id')", mode: 'simple' },
        }),
      ])

      expect(errors(wrapper)).toEqual([
        'databaseWorkflowActionType.staleReference',
      ])
    })

    test('a reference to an earlier action that returns nothing is marked', async () => {
      // The referenced action kept its place and its id, but a delete returns
      // no row, so the dispatch would fail the whole click on it.
      const wrapper = await mountList([
        { id: 1, type: 'local_baserow_delete_row', service: { table_id: 7 } },
        OPEN_URL({
          url: { formula: "get('previous_action.1.id')", mode: 'simple' },
        }),
      ])

      expect(errors(wrapper)).toEqual([
        'databaseWorkflowActionType.unreadableReference',
      ])
      expect(en.databaseWorkflowActionType.unreadableReference).toBe(
        'This action uses a result from an action that no longer returns one.'
      )
    })

    test('changing an earlier action to one that returns nothing marks the reference', async () => {
      const chained = OPEN_URL({
        url: { formula: "get('previous_action.1.id')", mode: 'simple' },
      })
      const wrapper = await mountList([CREATE(), chained])
      expect(errors(wrapper)).toEqual([])

      // The type dropdown keeps the action's id and its place, so nothing
      // about the reference itself changes.
      await wrapper.vm.onActionTypeChanged(0, 'open_url')
      await wrapper.setProps({ value: lastEmitted(wrapper) })

      // The retyped action has no url of its own yet, but it is what the user
      // is working on, so only what its change did to the action after it is
      // reported.
      expect(errors(wrapper)).toEqual([
        'databaseWorkflowActionType.unreadableReference',
      ])

      wrapper.vm.touch()
      await wrapper.vm.$nextTick()

      expect(errors(wrapper)).toEqual([
        'databaseWorkflowActionType.noUrl',
        'databaseWorkflowActionType.unreadableReference',
      ])
    })

    test('a newly chosen action is not marked before it is submitted', async () => {
      const wrapper = await mountList([])

      wrapper.vm.addAction('open_url')
      await wrapper.setProps({ value: lastEmitted(wrapper) })

      expect(errors(wrapper)).toEqual([])
      expect(wrapper.text()).not.toContain(
        'buttonFieldActionList.misconfigured'
      )
    })

    test('a newly chosen row action is not marked before it is submitted', async () => {
      // The type is picked before the table is, so an action that has just
      // been chosen is half configured for as long as that takes.
      const wrapper = await mountList([])

      wrapper.vm.addAction('local_baserow_create_row')
      await wrapper.setProps({ value: lastEmitted(wrapper) })

      expect(errors(wrapper)).toEqual([])
      expect(wrapper.text()).not.toContain(
        'buttonFieldActionList.misconfigured'
      )

      wrapper.vm.touch()
      await wrapper.vm.$nextTick()

      expect(errors(wrapper)).toEqual(['serviceType.errorNoTableSelected'])
      expect(wrapper.text()).toContain('buttonFieldActionList.misconfigured')
    })

    test('submitting the field form marks a newly chosen action', async () => {
      const wrapper = await mountList([])
      wrapper.vm.addAction('open_url')
      await wrapper.setProps({ value: lastEmitted(wrapper) })

      wrapper.vm.touch()
      await wrapper.vm.$nextTick()

      expect(errors(wrapper)).toEqual(['databaseWorkflowActionType.noUrl'])
      expect(wrapper.text()).toContain('buttonFieldActionList.misconfigured')
    })

    test('adding another action marks the one before it', async () => {
      const wrapper = await mountList([])
      wrapper.vm.addAction('open_url')
      await wrapper.setProps({ value: lastEmitted(wrapper) })

      wrapper.vm.addAction('open_url')
      await wrapper.setProps({ value: lastEmitted(wrapper) })

      // The first is marked, the one just added is not.
      expect(errors(wrapper)).toEqual(['databaseWorkflowActionType.noUrl'])
    })

    test('an action the editor loaded is marked straight away', async () => {
      const wrapper = await mountList([OPEN_URL({ url: null })])

      expect(errors(wrapper)).toEqual(['databaseWorkflowActionType.noUrl'])
    })

    test('submitting opens the first card whose own form refuses it', async () => {
      // A card the editor loaded starts collapsed, so an invalid formula
      // inside one blocks the save with nothing on screen to say why.
      const wrapper = await mountList([OPEN_URL(), OPEN_URL({ id: 3 })])
      const forms = wrapper.findAllComponents(ButtonFieldActionForm)
      vi.spyOn(forms[1].vm, 'isValid').mockReturnValue(false)

      expect(wrapper.vm.isExpanded(wrapper.props('value')[1])).toBe(false)

      wrapper.vm.touch()
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.isExpanded(wrapper.props('value')[1])).toBe(true)
      expect(wrapper.vm.isExpanded(wrapper.props('value')[0])).toBe(false)
    })
  })

  describe('the formula context an action form provides', () => {
    const ACTION = (over = {}) => ({
      id: 1,
      type: 'open_url',
      url: { formula: "'https://x.test'", mode: 'simple' },
      target: 'self',
      ...over,
    })

    const contextOf = (wrapper) =>
      wrapper.findComponent(ButtonFieldActionForm).vm.$.provides
        .databaseFormulaContext

    test('it reads its action through rather than copying it', async () => {
      const wrapper = await mountList([ACTION(), ACTION({ id: 2 })])
      const context = contextOf(wrapper)

      expect(context.workflowAction.id).toBe(1)
      expect(Object.keys(context)).toContain('workflowAction')

      await wrapper.setProps({
        value: [
          ACTION({ url: { formula: "'https://edited.test'", mode: 'simple' } }),
          ACTION({ id: 2 }),
        ],
      })

      // Read through rather than copied, so the same object answers with what
      // the list holds now.
      expect(context.workflowAction.url.formula).toBe("'https://edited.test'")
    })
  })

  describe('keyboard', () => {
    const ACTION = (over = {}) => ({
      id: 1,
      type: 'open_url',
      url: { formula: "'https://x.test'", mode: 'simple' },
      target: 'self',
      ...over,
    })

    test('the collapse control opens a card from the keyboard', async () => {
      const wrapper = await mountList([ACTION()])
      const action = wrapper.props('value')[0]

      expect(wrapper.vm.isExpanded(action)).toBe(false)

      await wrapper.find('[data-action-toggle]').trigger('keydown.enter')

      expect(wrapper.vm.isExpanded(action)).toBe(true)
    })

    test('the drag handle moves an action from the keyboard', async () => {
      // The sortable directive tracks the pointer, so without this there is no
      // keyboard path to reorder at all.
      const wrapper = await mountList([ACTION(), ACTION({ id: 2 })])

      await wrapper.findAll('[data-sortable-handle]')[0].trigger('keydown.down')

      expect(lastEmitted(wrapper).map((action) => action.id)).toEqual([2, 1])
    })

    test('a move past the end of the list changes nothing', async () => {
      const wrapper = await mountList([ACTION(), ACTION({ id: 2 })])

      await wrapper.findAll('[data-sortable-handle]')[1].trigger('keydown.down')

      expect(emittedCount(wrapper)).toBe(0)
    })
  })
})
