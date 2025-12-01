import { TestApp } from '@baserow/test/helpers/testApp'
import DateTimePickerElement from '@baserow/modules/builder/components/elements/components/DateTimePickerElement.vue'

describe('DateTimePickerElement', () => {
  let testApp = null
  let store = null

  beforeAll(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountComponent = ({ props = {}, slots = {}, provide = {} }) => {
    return testApp.mount(DateTimePickerElement, {
      propsData: props,
      slots,
      provide,
      stubs: {
        // <client-only> and <date-picker> are registered globally
        'client-only': { template: '<div><slot /></div>' },
        'date-picker': { template: '<input />' },
      },
    })
  }

  test.each([
    { date: { name: 'EU', format: 'DD/MM/YYYY' }, time: null },
    { date: { name: 'US', format: 'MM/DD/YYYY' }, time: null },
    { date: { name: 'ISO', format: 'YYYY-MM-DD' }, time: null },
    {
      date: { name: 'EU', format: 'DD/MM/YYYY' },
      time: { name: '24', format: 'HH:mm' },
    },
    {
      date: { name: 'EU', format: 'DD/MM/YYYY' },
      time: { name: '12', format: 'hh:mm A' },
    },
    {
      date: { name: 'US', format: 'MM/DD/YYYY' },
      time: { name: '24', format: 'HH:mm' },
    },
    {
      date: { name: 'US', format: 'MM/DD/YYYY' },
      time: { name: '12', format: 'hh:mm A' },
    },
    {
      date: { name: 'ISO', format: 'YYYY-MM-DD' },
      time: { name: '24', format: 'HH:mm' },
    },
    {
      date: { name: 'ISO', format: 'YYYY-MM-DD' },
      time: { name: '12', format: 'hh:mm A' },
    },
  ])('placeholder corresponds to date and time formats', async (format) => {
    const page = {
      id: 1,
      dataSources: [],
      elements: [],
    }
    const builder = {
      id: 1,
      theme: { primary_color: '#ccc' },
      pages: [page],
    }
    const workspace = {}
    const mode = 'public'
    const element = {
      id: 1,
      type: 'datetime_picker',
      required: true,
      default_value: '',
      date_format: format.date.name,
      include_time: !!format.time,
      time_format: format.time ? format.time.name : '24',
      page_id: page.id,
    }
    store.dispatch('element/forceCreate', { page, element })

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        currentPage: page,
        elementPage: page,
        mode,
        applicationContext: { builder, page, mode },
        element,
        workspace,
      },
    })

    const dateInput = wrapper
      .findComponent({ name: 'ABDateTimePicker' })
      .findAllComponents({ name: 'ABInput' })
      .at(0)
    expect(wrapper.element).toMatchSnapshot()
    expect(dateInput.attributes('placeholder')).toBe(format.date.format)

    if (format.time) {
      const timeInput = wrapper
        .findComponent({ name: 'ABDateTimePicker' })
        .findAllComponents({ name: 'ABInput' })
        .at(-1)
      expect(timeInput.exists()).toBe(true)
      expect(timeInput.attributes('placeholder')).toBe(format.time.format)
    }
  })
})
