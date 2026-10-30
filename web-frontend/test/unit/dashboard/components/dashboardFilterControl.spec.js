import { TestApp } from '@baserow/test/helpers/testApp'
import { flushPromises } from '@vue/test-utils'
import DashboardFilterControl from '@baserow/modules/dashboard/components/filter/DashboardFilterControl'

let wrapper, testApp, saveValues
beforeEach(() => {
  testApp = new TestApp()
  saveValues = vi.fn().mockResolvedValue(true)
})
afterEach(() => testApp.afterEach())
async function render({
  type = 'text',
  mode = 'dropdown',
  operator = 'equal',
  appliedValues = ['Design'],
  multiple = true,
  unavailable = [],
  editMode = false,
  canApply = true,
  canDuplicate = true,
  canDelete = true,
  busy = false,
} = {}) {
  wrapper = await testApp.mount(DashboardFilterControl, {
    global: { stubs: { Teleport: false } },
    props: {
      filter: { id: 1, label: 'Team', type, operator, mode, multiple },
      appliedValues,
      saveValues,
      editMode,
      canApply,
      canDuplicate,
      canDelete,
      busy,
      optionState: {
        results: ['Design', 'Sales'],
        unavailable,
        next: null,
        loading: false,
        error: false,
      },
    },
  })
  return wrapper
}

test.each(['empty', 'not_empty', 'is_even_and_whole'])(
  'activates %s without loading choices',
  async (operator) => {
    await render({
      type: operator === 'is_even_and_whole' ? 'number' : 'text',
      operator,
      appliedValues: [],
    })
    expect(wrapper.get('.dashboard-filter__value').text()).toBe(
      'dashboardFilter.inactive'
    )
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('options')).toBeUndefined()
    expect(testApp.body.find('.select__search').exists()).toBe(false)
    await testApp.body.get('input[type="checkbox"]').setValue(true)
    await testApp.body.get('form').trigger('submit')
    expect(saveValues.mock.calls).toEqual([[['true']]])
  }
)

test('discards unapplied dropdown changes on close and restores applied choices', async () => {
  await render()
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body.findAll('input[type="checkbox"]')[1].setValue(true)
  expect(saveValues).not.toHaveBeenCalled()
  await testApp.body.get('form').trigger('keydown', { key: 'Escape' })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  const boxes = testApp.body.findAll('input[type="checkbox"]')
  expect(boxes[0].element.checked).toBe(true)
  expect(boxes[1].element.checked).toBe(false)
  expect(wrapper.emitted('options')).toHaveLength(2)
})

test.each([true, false])(
  'keeps choices in their original order when selecting and deselecting (multiple: %s)',
  async (multiple) => {
    await render({ multiple, appliedValues: [] })
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    const choices = () =>
      testApp.body
        .findAll('.dashboard-filter__option-value')
        .map((choice) => choice.text())
    const toggleSales = async (checked) => {
      if (multiple) {
        await testApp.body
          .findAll('input[type="checkbox"]')[1]
          .setValue(checked)
      } else {
        await testApp.body
          .findAll('.dashboard-filter__single-choice')[1]
          .trigger('click')
      }
    }
    expect(choices()).toEqual(['Design', 'Sales'])
    await toggleSales(true)
    expect(choices()).toEqual(['Design', 'Sales'])
    await toggleSales(false)
    expect(choices()).toEqual(['Design', 'Sales'])
    expect(saveValues).not.toHaveBeenCalled()
  }
)

test('keeps a selected value missing from the loaded choices visible and removable', async () => {
  await render({
    appliedValues: ['Archived', 'Sales'],
    unavailable: ['Archived'],
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(
    testApp.body
      .findAll('.dashboard-filter__option-value')
      .map((choice) => choice.text())
  ).toEqual(['Design', 'Sales', 'Archived'])
  const boxes = testApp.body.findAll('input[type="checkbox"]')
  expect(boxes[1].element.checked).toBe(true)
  expect(boxes[2].element.checked).toBe(true)
  await boxes[2].setValue(false)
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[['Sales']]])
})

test('applies a cleared draft only after Update is pressed', async () => {
  await render()
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body.get('input[type="checkbox"]').setValue(false)
  expect(saveValues).not.toHaveBeenCalled()
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[[]]])
  expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
    'false'
  )
})

test('trims input on Apply and discards its unapplied edits', async () => {
  await render({ mode: 'input', appliedValues: [] })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body.get('input').setValue('  Design  ')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[['Design']]])
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(testApp.body.get('input').element.value).toBe('')
})

test('shows unavailable selections and lets them be removed', async () => {
  await render({ unavailable: ['Design'] })
  expect(wrapper.find('.dashboard-filter__info').exists()).toBe(true)
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(testApp.body.get('.dashboard-filter__unavailable').text()).toBe(
    'dashboardFilter.unavailable'
  )
  expect(testApp.body.get('input[type="checkbox"]').element.checked).toBe(true)
  await testApp.body.get('input[type="checkbox"]').setValue(false)
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[[]]])
})

test('exposes the unavailable explanation on keyboard focus', async () => {
  await render({ unavailable: ['Design'] })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  const badge = testApp.body.get('.dashboard-filter__unavailable')
  expect(badge.attributes('tabindex')).toBe('0')
  await badge.trigger('focus')
  expect(document.body.querySelector('.tooltip').textContent).toBe(
    'dashboardFilter.unavailableHelp'
  )
  await badge.trigger('blur')
  expect(document.body.querySelector('.tooltip')).toBeNull()
})

test('a single-choice dropdown replaces the previous value', async () => {
  await render({ multiple: false })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(testApp.body.find('input[type="checkbox"]').exists()).toBe(false)
  await testApp.body
    .findAll('.dashboard-filter__single-choice')[1]
    .trigger('click')
  await flushPromises()
  expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
    'true'
  )
  expect(testApp.body.get('[aria-pressed="true"]').text()).toBe('Sales')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[['Sales']]])
})

test('opens the positioned context and restores trigger focus when Escape cancels the draft', async () => {
  await render()
  const trigger = wrapper.get('.dropdown__selected')
  await trigger.trigger('click')
  await flushPromises()
  expect(trigger.attributes('aria-expanded')).toBe('true')
  expect(testApp.body.get('.dashboard-filter__context').isVisible()).toBe(true)
  await testApp.body.findAll('input[type="checkbox"]')[1].setValue(true)
  await testApp.body.get('form').trigger('keydown', { key: 'Escape' })
  await flushPromises()
  expect(trigger.attributes('aria-expanded')).toBe('false')
  expect(document.activeElement).toBe(trigger.element)
  expect(saveValues).not.toHaveBeenCalled()
  await trigger.trigger('click')
  await flushPromises()
  expect(
    testApp.body.findAll('input[type="checkbox"]')[1].element.checked
  ).toBe(false)
})

test('clears the applied selection without opening the picker', async () => {
  await render()
  await wrapper.get('[aria-label="dashboardFilter.clear"]').trigger('click')
  await flushPromises()
  expect(saveValues.mock.calls).toEqual([[[]]])
  expect(wrapper.emitted('options')).toBeUndefined()
  expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
    'false'
  )
})

test('shows shared selections without allowing a viewer to change or clear them', async () => {
  await render({ canApply: false })
  expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
  const trigger = wrapper.get('.dropdown__selected')
  expect(trigger.element.disabled).toBe(true)
  expect(wrapper.find('[aria-label="dashboardFilter.clear"]').exists()).toBe(
    false
  )
  await trigger.trigger('click')
  expect(trigger.attributes('aria-expanded')).toBe('false')
  expect(wrapper.emitted('options')).toBeUndefined()
  expect(saveValues).not.toHaveBeenCalled()
})

test('blocks applying and clearing while a selection is saving', async () => {
  await render()
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body.findAll('input[type="checkbox"]')[1].setValue(true)
  await wrapper.setProps({ busy: true })
  await flushPromises()
  expect(wrapper.get('.dropdown__selected').element.disabled).toBe(true)
  expect(testApp.body.get('button[type="submit"]').classes()).toContain(
    'button--loading'
  )
  const clear = wrapper.get('[aria-label="dashboardFilter.clear"]')
  expect(clear.element.disabled).toBe(true)
  await clear.trigger('click')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues).not.toHaveBeenCalled()
})

test('keeps permitted configuration actions available without selection update permission', async () => {
  await render({ editMode: true, canApply: false })
  await wrapper.get('[aria-label="dashboardFilter.actions"]').trigger('click')
  await flushPromises()
  await testApp.body.get('button:has(.iconoir-copy)').trigger('click')
  expect(wrapper.emitted('duplicate')).toEqual([[]])
})

test('selects the filter settings in edit mode without opening the picker', async () => {
  await render({ editMode: true })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(wrapper.emitted('select')).toHaveLength(1)
  expect(wrapper.emitted('options')).toBeUndefined()
  expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
    'false'
  )
})

test('opens the actions menu without selecting the filter and restores focus on Escape', async () => {
  await render({ editMode: true })
  const trigger = wrapper.get('[aria-label="dashboardFilter.actions"]')
  await trigger.trigger('click')
  await flushPromises()
  expect(wrapper.emitted('select')).toBeUndefined()
  expect(wrapper.emitted('options')).toBeUndefined()
  const remove = testApp.body.get('.context__menu-item-link--delete')
  expect(remove.text()).toBe('action.delete')
  expect(remove.element.parentElement.classList).toContain(
    'context__menu-item--with-separator'
  )
  const duplicate = testApp.body.get('button:has(.iconoir-copy)')
  expect(duplicate.text()).toBe('action.duplicate')
  expect(document.activeElement).toBe(duplicate.element)
  await remove.trigger('keydown', { key: 'Escape' })
  await flushPromises()
  expect(trigger.attributes('aria-expanded')).toBe('false')
  expect(document.activeElement).toBe(trigger.element)
  expect(wrapper.emitted('delete')).toBeUndefined()
  await trigger.trigger('click')
  await flushPromises()
  await testApp.body.get('.context__menu-item-link--delete').trigger('click')
  expect(wrapper.emitted('delete')).toEqual([[]])
  expect(trigger.attributes('aria-expanded')).toBe('false')
})

test.each([
  { editMode: false },
  { editMode: true, canDuplicate: false, canDelete: false },
])(
  'hides actions outside edit mode or without either permission: %j',
  async (props) => {
    await render(props)
    expect(
      wrapper.find('[aria-label="dashboardFilter.actions"]').exists()
    ).toBe(false)
    expect(testApp.body.find('.context__menu-item-link--delete').exists()).toBe(
      false
    )
  }
)

test('filters loaded choices immediately without requesting options or losing selections', async () => {
  await render()
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  const choices = () =>
    testApp.body
      .findAll('.dashboard-filter__option-value')
      .map((choice) => choice.text())
  const search = testApp.body.get('input[type="text"]')
  await search.setValue('sAL')
  expect(choices()).toEqual(['Sales'])
  expect(testApp.body.find('[role="status"]').exists()).toBe(false)
  expect(wrapper.emitted('options')).toHaveLength(1)
  expect(saveValues).not.toHaveBeenCalled()

  await search.setValue('missing')
  expect(choices()).toEqual([])
  expect(testApp.body.text()).toContain('dashboardFilter.noOptions')
  await search.setValue('')
  expect(choices()).toEqual(['Design', 'Sales'])
  expect(testApp.body.get('input[type="checkbox"]').element.checked).toBe(true)
  expect(wrapper.emitted('options')).toHaveLength(1)
})

test('keeps an unavailable option named like an object property readable', async () => {
  await render({
    appliedValues: ['constructor'],
    unavailable: ['constructor'],
    multiple: false,
  })
  await wrapper.setProps({
    optionState: {
      results: [],
      unavailable: ['constructor'],
      next: null,
      loading: false,
      error: false,
    },
  })
  expect(wrapper.get('.dashboard-filter__value').text()).toBe('constructor')
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body.get('.select__search-input').setValue('constructor')
  expect(testApp.body.get('.dashboard-filter__option-value').text()).toBe(
    'constructor'
  )
})

test.each([
  ['ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE', 'optionsTooLarge'],
  ['ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED', 'optionsExpired'],
])('explains %s and retries from the beginning', async (errorCode, message) => {
  await render()
  await wrapper.setProps({
    optionState: {
      results: ['Design'],
      next: 'stale-cursor',
      unavailable: [],
      loading: false,
      error: true,
      errorCode,
    },
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(testApp.body.get('[role="status"]').text()).toContain(
    `dashboardFilter.${message}`
  )
  expect(testApp.body.find('.dashboard-filter__more').exists()).toBe(false)
  await testApp.body.get('[role="status"] button').trigger('click')
  expect(wrapper.emitted('options').at(-1)).toEqual([
    { more: false, selected: ['Design'] },
  ])
})

test.each([
  { canDuplicate: true, canDelete: false, action: 'duplicate' },
  { canDuplicate: false, canDelete: true, action: 'delete' },
])(
  'only exposes and focuses the permitted $action action',
  async (permissions) => {
    await render({ editMode: true, ...permissions })
    await wrapper.get('[aria-label="dashboardFilter.actions"]').trigger('click')
    await flushPromises()
    const options = testApp.body.findAll('.dashboard-filter__menu-option')
    expect(options).toHaveLength(1)
    expect(options[0].text()).toBe(`action.${permissions.action}`)
    expect(document.activeElement).toBe(options[0].element)
    expect(
      testApp.body.find('.context__menu-item--with-separator').exists()
    ).toBe(false)
    await options[0].trigger('click')
    expect(wrapper.emitted(permissions.action)).toEqual([[]])
    expect(wrapper.emitted('select')).toBeUndefined()
  }
)

test('prevents opening the actions menu while a mutation is pending', async () => {
  await render({ editMode: true, busy: true })
  const trigger = wrapper.get('[aria-label="dashboardFilter.actions"]')
  expect(trigger.attributes('disabled')).toBeDefined()
  expect(wrapper.findAll('.dropdown__toggle-loading')).toHaveLength(1)
  expect(wrapper.find('.button-icon--loading').exists()).toBe(false)
  await trigger.trigger('click')
  expect(trigger.attributes('aria-expanded')).toBe('false')
  expect(wrapper.emitted('duplicate')).toBeUndefined()
  expect(wrapper.emitted('delete')).toBeUndefined()
})

test.each(['0', '-12.345', '123456.789'])(
  'applies a number input immediately without changing its precision: %s',
  async (value) => {
    await render({
      type: 'number',
      operator: 'higher_than',
      mode: 'input',
      appliedValues: ['100'],
    })
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    const input = testApp.body.get('input[type="number"]')
    expect(testApp.body.get('form').attributes('novalidate')).toBeDefined()
    await input.setValue(value)
    await testApp.body.get('form').trigger('submit')
    expect(saveValues.mock.calls).toEqual([[[value]]])
    expect(wrapper.emitted('options')).toBeUndefined()
  }
)

test('keeps a date contains input as text', async () => {
  await render({
    type: 'date',
    operator: 'contains',
    mode: 'input',
    appliedValues: [],
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(testApp.body.find('.filters__multi-value').exists()).toBe(false)
  await testApp.body.get('input[type="text"]').setValue('2026-10')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[['2026-10']]])
})

test('applies a day-of-month number using the Builder timezone format', async () => {
  await render({
    type: 'date',
    operator: 'date_equals_day_of_month',
    mode: 'input',
    appliedValues: [],
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body.get('input[type="number"]').setValue('15')
  await testApp.body.get('form').trigger('submit')
  const applied = saveValues.mock.calls[0][0]
  expect(applied).toHaveLength(1)
  expect(applied[0]).toMatch(/\?15$/)
  await wrapper.setProps({ appliedValues: applied })
  expect(wrapper.get('.dashboard-filter__value').text()).toBe('15')
})

test('applies raw ISO values from a date dropdown without changing their format', async () => {
  await render({
    type: 'date',
    operator: 'date_is',
    multiple: false,
    appliedValues: [],
  })
  await wrapper.setProps({
    optionState: {
      results: ['2026-10-01', '2026-10-26'],
      unavailable: [],
      next: null,
      loading: false,
      error: false,
    },
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body
    .findAll('.dashboard-filter__single-choice')[1]
    .trigger('click')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[['2026-10-26']]])
})

test('clears an applied exact date when its input is emptied', async () => {
  await render({
    type: 'date',
    operator: 'date_is',
    mode: 'input',
    appliedValues: ['Asia/Dubai?2026-10-26?exact_date'],
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  await testApp.body.get('.filters__value-input input').setValue('')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[[]]])
})

test('rejects an invalid exact date after editing a valid draft', async () => {
  await render({
    type: 'date',
    operator: 'date_is',
    mode: 'input',
    appliedValues: ['Asia/Dubai?2026-10-01?exact_date'],
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  const input = testApp.body.get('.filters__value-input input')
  await input.setValue('2026-10-26')
  expect(testApp.body.get('button[type="submit"]').element.disabled).toBe(false)
  await input.setValue('2026-13-41')
  expect(testApp.body.get('button[type="submit"]').element.disabled).toBe(true)
  expect(testApp.body.text()).toContain('dashboardFilter.invalidDateValue')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues).not.toHaveBeenCalled()
  await input.setValue('2026-10-27')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([
    [['Asia/Dubai?2026-10-27?exact_date']],
  ])
})

test('rejects an invalid relative count and clears it without losing its timezone', async () => {
  await render({
    type: 'date',
    operator: 'date_is',
    mode: 'input',
    appliedValues: ['America/New_York?7?nr_days_ago'],
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  const input = testApp.body.get('.filters__combined-value-input input')
  await input.setValue('1.5')
  expect(testApp.body.get('button[type="submit"]').element.disabled).toBe(true)
  await testApp.body.get('form').trigger('submit')
  expect(saveValues).not.toHaveBeenCalled()
  await input.setValue('')
  expect(testApp.body.get('button[type="submit"]').element.disabled).toBe(false)
  await input.setValue('0')
  await testApp.body.get('form').trigger('submit')
  expect(saveValues.mock.calls).toEqual([[['America/New_York?0?nr_days_ago']]])
})

test('picks an exact date with the shared Builder input without implicitly applying a value', async () => {
  await render({
    type: 'date',
    operator: 'date_is',
    mode: 'input',
    appliedValues: [],
  })
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(testApp.body.find('.filters__multi-value').exists()).toBe(true)
  expect(saveValues).not.toHaveBeenCalled()
  expect(testApp.body.get('button[type="submit"]').element.disabled).toBe(true)
  await testApp.body.get('.filters__value-input input').setValue('2026-10-26')
  await testApp.body.get('form').trigger('submit')
  const applied = saveValues.mock.calls[0][0]
  expect(applied).toHaveLength(1)
  expect(applied[0]).toMatch(/\?2026-10-26\?exact_date$/)
  await wrapper.setProps({ appliedValues: applied })
  expect(wrapper.get('.dashboard-filter__value').text()).toContain('2026-10-26')
  expect(wrapper.get('.dashboard-filter__value').text()).not.toContain('?')
  await wrapper.get('.dropdown__selected').trigger('click')
  await flushPromises()
  expect(testApp.body.get('.filters__value-input input').element.value).toBe(
    '2026-10-26'
  )
})

test.each([
  ['viewFilter.today', null, /\?\?today$/],
  ['viewFilter.nrDaysAgo', '7', /\?7\?nr_days_ago$/],
])(
  'applies the shared relative date choice %s',
  async (label, value, expected) => {
    await render({
      type: 'date',
      operator: 'date_is',
      mode: 'input',
      appliedValues: [],
    })
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    await testApp.body
      .get('.filters__multi-value-operator .dropdown__selected')
      .trigger('click')
    await flushPromises()
    await testApp.body
      .findAll('.select__item-link')
      .find((item) => item.text() === label)
      .trigger('click')
    if (value !== null) {
      await testApp.body
        .get('.filters__combined-value-input input')
        .setValue(value)
    }
    await testApp.body.get('form').trigger('submit')
    const applied = saveValues.mock.calls[0][0]
    expect(applied).toHaveLength(1)
    expect(applied[0]).toMatch(expected)
    await wrapper.setProps({ appliedValues: applied })
    expect(wrapper.get('.dashboard-filter__value').text()).toContain(label)
    expect(wrapper.get('.dashboard-filter__value').text()).not.toContain('?')
  }
)
