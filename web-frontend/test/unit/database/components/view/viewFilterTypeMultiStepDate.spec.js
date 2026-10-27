import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import ViewFilterTypeMultiStepDate from '@baserow/modules/database/components/view/ViewFilterTypeMultiStepDate'

describe('ViewFilterTypeMultiStepDate draft contract', () => {
  let testApp
  beforeEach(() => {
    testApp = new TestApp()
  })
  afterEach(() => testApp.afterEach())

  const mountPicker = (value, dateFormat = 'ISO') =>
    testApp.mount(ViewFilterTypeMultiStepDate, {
      global: { stubs: { Teleport: false } },
      props: {
        filter: { field: 1, type: 'date_is', value },
        fields: [{ id: 1, type: 'date', date_format: dateFormat }],
        disabled: false,
        readOnly: false,
      },
    })

  test('publishes invalid and cleared drafts without changing legacy input events', async () => {
    const wrapper = await mountPicker('Asia/Dubai?2026-10-01?exact_date')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      {
        value: 'Asia/Dubai?2026-10-01?exact_date',
        valid: true,
        empty: false,
      },
    ])
    expect(wrapper.emitted('input')).toBeUndefined()

    const input = wrapper.get('.filters__value-input input')
    await input.setValue('2026-10-26')
    expect(wrapper.emitted('input')).toEqual([
      ['Asia/Dubai?2026-10-26?exact_date'],
    ])
    await input.setValue('2026-13-41')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      {
        value: 'Asia/Dubai?2026-13-41?exact_date',
        valid: false,
        empty: false,
      },
    ])
    await input.setValue('')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      { value: 'Asia/Dubai??exact_date', valid: true, empty: true },
    ])
    expect(wrapper.emitted('input')).toEqual([
      ['Asia/Dubai?2026-10-26?exact_date'],
    ])
  })

  test.each([
    ['EU', '26/10/2026'],
    ['US', '10/26/2026'],
  ])(
    'normalizes the %s date format while retaining its timezone',
    async (format, value) => {
      const wrapper = await mountPicker('America/New_York??exact_date', format)
      await wrapper.get('.filters__value-input input').setValue(value)
      expect(wrapper.emitted('draft-change').at(-1)).toEqual([
        {
          value: 'America/New_York?2026-10-26?exact_date',
          valid: true,
          empty: false,
        },
      ])
      expect(wrapper.emitted('input')).toEqual([
        ['America/New_York?2026-10-26?exact_date'],
      ])
    }
  )

  test('keeps the legacy invalid Enter and operator-switch input payloads', async () => {
    const wrapper = await mountPicker('Asia/Dubai?2026-10-26?exact_date')
    const input = wrapper.get('.filters__value-input input')
    await input.setValue('invalid')
    expect(wrapper.emitted('input')).toBeUndefined()
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('input')).toEqual([
      ['Asia/Dubai?invalid?exact_date'],
    ])
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    await testApp.body
      .findAll('.select__item-link')
      .find((item) => item.text() === 'viewFilter.today')
      .trigger('click')
    expect(wrapper.emitted('input').at(-1)).toEqual(['Asia/Dubai??today'])
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      { value: 'Asia/Dubai??today', valid: true, empty: false },
    ])
  })

  test('publishes relative operator drafts and preserves their legacy input payloads', async () => {
    const wrapper = await mountPicker('Asia/Dubai?2026-10-26?exact_date')
    const chooseOperator = async (label) => {
      await wrapper.get('.dropdown__selected').trigger('click')
      await flushPromises()
      await testApp.body
        .findAll('.select__item-link')
        .find((item) => item.text() === label)
        .trigger('click')
    }
    await chooseOperator('viewFilter.today')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      { value: 'Asia/Dubai??today', valid: true, empty: false },
    ])
    await chooseOperator('viewFilter.nrDaysAgo')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      { value: 'Asia/Dubai??nr_days_ago', valid: true, empty: true },
    ])
    await wrapper.get('.filters__combined-value-input input').setValue('7')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      { value: 'Asia/Dubai?7?nr_days_ago', valid: true, empty: false },
    ])
    await wrapper.get('.filters__combined-value-input input').setValue('1.5')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      { value: 'Asia/Dubai?1.5?nr_days_ago', valid: false, empty: false },
    ])
    await wrapper.get('.filters__combined-value-input input').setValue('')
    expect(wrapper.emitted('draft-change').at(-1)).toEqual([
      { value: 'Asia/Dubai??nr_days_ago', valid: true, empty: true },
    ])
    expect(wrapper.emitted('input')).toEqual([
      ['Asia/Dubai??today'],
      ['Asia/Dubai??nr_days_ago'],
      ['Asia/Dubai?7?nr_days_ago'],
      ['Asia/Dubai?1.5?nr_days_ago'],
      ['Asia/Dubai??nr_days_ago'],
    ])
  })
})
