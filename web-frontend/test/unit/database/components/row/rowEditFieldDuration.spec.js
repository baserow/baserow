import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditFieldDuration from '@baserow/modules/database/components/row/RowEditFieldDuration'

describe('RowEditFieldDuration', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const field = {
    id: 1,
    name: 'Duration',
    type: 'duration',
    duration_format: 'h:mm',
  }

  const mountField = (props = {}) =>
    testApp.mount(RowEditFieldDuration, {
      props: {
        field,
        value: null,
        readOnly: false,
        required: true,
        touched: false,
        workspaceId: 0,
        ...props,
      },
    })

  test('a required field saves a valid duration entered from empty', async () => {
    const wrapper = await mountField({ touched: true })
    const input = wrapper.find('input')

    await input.trigger('focus')
    await input.setValue('14:30')
    await input.trigger('keyup')

    expect(wrapper.text()).not.toContain('error.requiredField')

    await input.trigger('blur')

    expect(wrapper.emitted('update')).toEqual([[52_200, null]])
  })

  test('an empty required field still shows the required error when touched', async () => {
    const wrapper = await mountField({ touched: true })

    expect(wrapper.text()).toContain('error.requiredField')
  })

  test('invalid text shows the duration format error, not required', async () => {
    const wrapper = await mountField({ touched: true })
    const input = wrapper.find('input')

    await input.trigger('focus')
    await input.setValue('14:')
    await input.trigger('keyup')

    expect(wrapper.text()).toContain('fieldErrors.invalidDuration')
    expect(wrapper.text()).not.toContain('error.requiredField')
  })
})
