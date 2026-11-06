import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditFieldDate from '@baserow/modules/database/components/row/RowEditFieldDate'

describe('RowEditFieldDate', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('saves a date entered without key presses', async () => {
    const wrapper = await testApp.mount(RowEditFieldDate, {
      props: {
        field: {
          id: 1,
          name: 'Date',
          type: 'date',
          date_format: 'ISO',
          date_include_time: false,
          date_force_timezone: null,
        },
        value: null,
        readOnly: false,
        required: true,
        touched: true,
        workspaceId: 0,
      },
      global: { stubs: { DatePicker: true } },
    })
    const input = wrapper.find('input')

    await input.trigger('focus')
    await input.setValue('2026-11-05')
    await input.trigger('blur')

    expect(wrapper.text()).not.toContain('error.requiredField')
    expect(wrapper.emitted('update')).toEqual([['2026-11-05', null]])
  })
})
