import { defineComponent, nextTick, reactive } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import CoreHTTPDataSourceServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPDataSourceServiceForm'

const FormGroupStub = defineComponent({
  name: 'FormGroup',
  props: {
    label: { type: String, required: false, default: '' },
  },
  template: '<div class="form-group-stub" :data-label="label"><slot /></div>',
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: {
    modelValue: { required: false, default: null },
  },
  emits: ['update:modelValue'],
  template: '<div />',
})

async function mountComponent(
  defaultValues = {},
  dataSourceTest = null,
  service = null
) {
  return await mountSuspended(CoreHTTPDataSourceServiceForm, {
    props: { defaultValues, service },
    global: {
      provide: dataSourceTest ? { dataSourceTest } : {},
      stubs: {
        FormGroup: FormGroupStub,
        InjectedFormulaInput: InjectedFormulaInputStub,
      },
      mocks: {
        $t: (key) => key,
      },
    },
  })
}

const findTab = (wrapper, title) =>
  wrapper.findAll('.tabs__item').find((tab) => tab.text().includes(title))

const openTab = async (wrapper, title) => {
  await findTab(wrapper, title).trigger('click')
  await nextTick()
}

const listPathGroup = (wrapper) =>
  wrapper.find('[data-label="coreHTTPDataSourceServiceForm.listPath"]')

const findButton = (wrapper, label) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))

describe('CoreHTTPDataSourceServiceForm', () => {
  test('the tabs show what each holds', async () => {
    const wrapper = await mountComponent({
      type: 'http_get',
      headers: [{ id: 1, key: 'a', value: { formula: '' } }],
      query_params: [],
      timeout: 12,
    })
    await flushPromises()

    expect(
      findTab(wrapper, 'coreHTTPRequestServiceForm.queryParams').text()
    ).toContain('0')
    expect(
      findTab(wrapper, 'coreHTTPRequestServiceForm.headers').text()
    ).toContain('1')
    expect(
      findTab(wrapper, 'coreHTTPDataSourceServiceForm.response').text()
    ).toContain('coreHTTPDataSourceServiceForm.oneRecord')
    expect(
      findTab(wrapper, 'coreHTTPDataSourceServiceForm.settings').text()
    ).toContain('12 s')
  })

  test('a single record data source has no list path', async () => {
    const wrapper = await mountComponent({ type: 'http_get' })
    await flushPromises()
    await openTab(wrapper, 'coreHTTPDataSourceServiceForm.response')

    expect(wrapper.findAll('.radio-card')).toHaveLength(2)
    expect(wrapper.find('.radio-card--selected').text()).toContain(
      'coreHTTPDataSourceServiceForm.oneRecord'
    )
    expect(listPathGroup(wrapper).exists()).toBe(false)
  })

  test('a list data source shows its list path', async () => {
    const wrapper = await mountComponent({
      type: 'http_get',
      returns_list: true,
      list_path: 'data.items',
    })
    await flushPromises()

    expect(
      findTab(wrapper, 'coreHTTPDataSourceServiceForm.response').text()
    ).toContain('coreHTTPDataSourceServiceForm.aList')
    await openTab(wrapper, 'coreHTTPDataSourceServiceForm.response')

    expect(wrapper.find('.radio-card--selected').text()).toContain(
      'coreHTTPDataSourceServiceForm.listOfRecords'
    )
    expect(listPathGroup(wrapper).find('input').element.value).toBe(
      'data.items'
    )
  })

  test('choosing the shape sets whether it returns a list', async () => {
    const wrapper = await mountComponent({
      type: 'http_get',
      url: { formula: "'https://x'" },
      timeout: 12,
    })
    await flushPromises()
    await openTab(wrapper, 'coreHTTPDataSourceServiceForm.response')

    await wrapper.findAll('.radio-card')[1].trigger('click')
    await nextTick()

    expect(listPathGroup(wrapper).exists()).toBe(true)
    expect(wrapper.emitted('values-changed').at(-1)[0]).toMatchObject({
      returns_list: true,
      url: { formula: "'https://x'" },
      timeout: 12,
    })

    await wrapper.findAll('.radio-card')[0].trigger('click')
    await nextTick()

    expect(listPathGroup(wrapper).exists()).toBe(false)
    const singleValues = wrapper.emitted('values-changed').at(-1)[0]
    expect(singleValues.returns_list).toBe(false)
    expect(singleValues).not.toHaveProperty('list_path')
    expect(singleValues).not.toHaveProperty('type')
  })

  test('only a list data source sends a list path', async () => {
    const single = await mountComponent({ type: 'http_get', timeout: 12 })
    await flushPromises()
    await openTab(single, 'coreHTTPDataSourceServiceForm.settings')
    await single.find('input[type="number"]').setValue('15')
    await nextTick()

    expect(single.emitted('values-changed').at(-1)[0]).not.toHaveProperty(
      'list_path'
    )
    expect(single.vm.getFormValues()).not.toHaveProperty('list_path')

    const list = await mountComponent({
      type: 'http_get',
      returns_list: true,
      list_path: 'data.items',
    })
    await flushPromises()

    expect(list.vm.getFormValues()).toMatchObject({ list_path: 'data.items' })
  })

  test('chooses the records in the response of the last test', async () => {
    const response = { data: { items: [{ id: 1 }] }, total: 1 }
    const wrapper = await mountComponent(
      { type: 'http_get', timeout: 12 },
      null,
      { id: 1, type: 'http_get', sample_data: { data: response } }
    )
    await flushPromises()
    await openTab(wrapper, 'coreHTTPDataSourceServiceForm.response')

    expect(wrapper.findAll('.radio-card')).toHaveLength(0)
    const items = wrapper
      .findAll('.http-response-picker__row')
      .find((row) => row.text().startsWith('items'))
    await items.trigger('click')

    expect(wrapper.emitted('values-changed').at(-1)[0]).toMatchObject({
      returns_list: true,
      list_path: 'data.items',
      timeout: 12,
    })
    expect(
      findTab(wrapper, 'coreHTTPDataSourceServiceForm.response').text()
    ).toContain('coreHTTPDataSourceServiceForm.aList')

    // A list path which isn't in the response empties the sample data until
    // it's tested again: the response stays.
    await wrapper.setProps({
      service: {
        id: 1,
        type: 'http_get',
        returns_list: true,
        sample_data: null,
      },
    })
    expect(wrapper.find('.http-response-picker').exists()).toBe(true)
    expect(
      wrapper.find('.http-response-picker__row--selected').text()
    ).toContain('httpResponsePicker.records')
  })

  test('a list data source chooses in the response its test kept', async () => {
    const wrapper = await mountComponent(
      { type: 'http_get', returns_list: true, list_path: 'data.items' },
      null,
      {
        id: 1,
        type: 'http_get',
        returns_list: true,
        sample_data: {
          data: {
            results: [{ id: 1 }],
            has_next_page: false,
            response: { data: { items: [{ id: 1 }] } },
          },
        },
      }
    )
    await flushPromises()
    await openTab(wrapper, 'coreHTTPDataSourceServiceForm.response')

    expect(listPathGroup(wrapper).exists()).toBe(false)
    expect(wrapper.find('.http-response-picker__row--selected').text()).toMatch(
      /^items/
    )
  })

  test('another type of data source can be switched to an HTTP request', async () => {
    // The saved data source is still the other type until the switch is saved.
    const wrapper = await mountComponent({ type: 'http_get' }, null, {
      id: 1,
      type: 'local_baserow_list_rows',
      sample_data: { data: { results: [{ id: 1 }] } },
    })
    await flushPromises()
    await openTab(wrapper, 'coreHTTPDataSourceServiceForm.response')

    expect(wrapper.find('.http-response-picker').exists()).toBe(false)
    expect(wrapper.findAll('.radio-card')).toHaveLength(2)
  })

  test('a value which is not valid blocks the form from any tab', async () => {
    const wrapper = await mountComponent({
      type: 'http_get',
      headers: [{ id: 1, key: 'not valid', value: { formula: '' } }],
      timeout: 12,
    })
    await flushPromises()
    const headersTab = () =>
      findTab(wrapper, 'coreHTTPRequestServiceForm.headers')

    expect(headersTab().find('.iconoir-warning-circle').exists()).toBe(true)
    expect(
      findTab(wrapper, 'coreHTTPDataSourceServiceForm.settings')
        .find('.iconoir-warning-circle')
        .exists()
    ).toBe(false)

    // The header isn't shown from the settings, but still blocks the form.
    await openTab(wrapper, 'coreHTTPDataSourceServiceForm.settings')
    expect(wrapper.find('.http-data-source-form__timeout').exists()).toBe(true)
    expect(wrapper.vm.isFormValid(true)).toBe(false)

    // Showing the errors opens the tab with the header.
    wrapper.vm.touch(true)
    await nextTick()
    expect(headersTab().classes()).toContain('tabs__item--active')
    expect(wrapper.find('.http-data-source-form__timeout').exists()).toBe(false)
    expect(wrapper.find('.error').text()).toBe(
      'coreHTTPRequestServiceForm.nameFieldInvalid'
    )
  })

  test('a timeout which is not valid is shown in its tab', async () => {
    const wrapper = await mountComponent({ type: 'http_get', timeout: 99 })
    await flushPromises()
    const settingsTab = () =>
      findTab(wrapper, 'coreHTTPDataSourceServiceForm.settings')

    expect(settingsTab().find('.iconoir-warning-circle').exists()).toBe(true)
    expect(wrapper.vm.isFormValid(true)).toBe(false)

    wrapper.vm.touch(true)
    await nextTick()
    expect(settingsTab().classes()).toContain('tabs__item--active')
  })

  test('touching a valid form stays on the open tab', async () => {
    const wrapper = await mountComponent({ type: 'http_get', timeout: 12 })
    await flushPromises()
    await openTab(wrapper, 'coreHTTPRequestServiceForm.headers')

    wrapper.vm.touch(true)
    await nextTick()
    expect(
      findTab(wrapper, 'coreHTTPRequestServiceForm.headers').classes()
    ).toContain('tabs__item--active')
    expect(wrapper.find('.iconoir-warning-circle').exists()).toBe(false)
  })

  test('adds a header row', async () => {
    const wrapper = await mountComponent({ type: 'http_get', headers: [] })
    await flushPromises()
    await openTab(wrapper, 'coreHTTPRequestServiceForm.headers')

    await findButton(wrapper, 'coreHTTPRequestServiceForm.addHeader').trigger(
      'click'
    )
    await nextTick()

    expect(wrapper.emitted('values-changed').at(-1)[0].headers).toMatchObject([
      { key: 'header1', value: { formula: '', mode: 'simple' } },
    ])
  })

  test('tests from the request bar when the data source form allows it', async () => {
    const dataSourceTest = reactive({ isLoading: false, test: vi.fn() })
    const wrapper = await mountComponent({ type: 'http_get' }, dataSourceTest)
    await flushPromises()

    await findButton(wrapper, 'coreHTTPDataSourceServiceForm.test').trigger(
      'click'
    )
    expect(dataSourceTest.test).toHaveBeenCalledTimes(1)

    const withoutTest = await mountComponent({ type: 'http_get' })
    await flushPromises()
    expect(
      findButton(withoutTest, 'coreHTTPDataSourceServiceForm.test')
    ).toBeUndefined()
  })
})
