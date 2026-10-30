import { vi } from 'vitest'
import { reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import MockAdapter from 'axios-mock-adapter'

import DataSourceTestForm from '@baserow/modules/builder/components/dataSource/DataSourceTestForm'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

const SampleDataModalStub = {
  name: 'SampleDataModal',
  props: {
    sampleData: { type: [Object, Array, String], default: null },
    title: { type: String, default: '' },
    subtitle: { type: String, default: '' },
  },
  methods: { show() {} },
  template: '<div class="sample-data-modal-stub" />',
}

describe('DataSourceTestForm', () => {
  let mock = null
  let store = null

  beforeEach(() => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
    vi.spyOn(
      DataProviderType,
      'getAllDataSourceDispatchContext'
    ).mockReturnValue({ page_parameter: { id: 1 } })
  })

  afterEach(() => {
    mock.restore()
    vi.restoreAllMocks()
  })

  const mountComponent = (page, extraProps = {}, provide = {}) =>
    mountSuspended(DataSourceTestForm, {
      props: { dataSource: page.dataSources[0], page, ...extraProps },
      global: {
        provide: { applicationContext: { builder: { id: 1 } }, ...provide },
        stubs: { SampleDataModal: SampleDataModalStub },
      },
    })

  const createPage = (sampleData) => ({
    id: 42,
    dataSources: [
      {
        id: 7,
        name: 'Products',
        type: 'local_baserow_get_row',
        sample_data: sampleData,
      },
    ],
    _: {},
  })

  test('asks to test a data source that has no sample data', async () => {
    const wrapper = await mountComponent(createPage(null))

    expect(wrapper.find('.data-source-test-form__code').exists()).toBe(false)
    expect(wrapper.find('.data-source-test-form__empty').text()).toBe(
      'dataSourceTestForm.testDescription'
    )
    expect(wrapper.text()).toContain('dataSourceTestForm.buttonLabelTest')
  })

  test('shows the sample data of a successful test', async () => {
    const page = createPage(null)
    mock
      .onPost('builder/data-source/7/simulate-dispatch/', {
        metadata: { page_parameter: { id: 1 } },
      })
      .replyOnce(200, {
        ...page.dataSources[0],
        sample_data: { data: { name: 'Lamp' }, status: 200 },
      })

    const wrapper = await mountComponent(page)
    await wrapper.find('button').trigger('click')
    await flushPromises()

    // The modal passes the data source from the store, which the test updated.
    await wrapper.setProps({
      dataSource: store.getters['dataSource/getPageDataSourceById'](page, 7),
    })

    const code = wrapper.find('.data-source-test-form__code')
    expect(JSON.parse(code.text())).toEqual({ name: 'Lamp' })
    expect(code.classes()).not.toContain('data-source-test-form__code--error')
    expect(wrapper.text()).toContain('dataSourceTestForm.succeeded')
    expect(wrapper.text()).toContain('dataSourceTestForm.buttonLabelTestAgain')
  })

  test('shows the error of a failed test', async () => {
    const page = createPage({ data: { name: 'Lamp' }, status: 200 })
    mock.onPost('builder/data-source/7/simulate-dispatch/').replyOnce(400, {
      error: 'ERROR_SERVICE_IMPROPERLY_CONFIGURED',
      detail: 'Row 999 does not exist.',
    })

    const wrapper = await mountComponent(page)
    await wrapper.find('button').trigger('click')
    await flushPromises()

    const code = wrapper.find('.data-source-test-form__code')
    expect(code.text()).toBe('Row 999 does not exist.')
    expect(code.classes()).toContain('data-source-test-form__code--error')
    expect(wrapper.text()).toContain('dataSourceTestForm.failed')
  })

  test('runs beforeTest first, and skips the test when it says so', async () => {
    const page = createPage(null)
    const calls = []
    mock.onPost('builder/data-source/7/simulate-dispatch/').reply(() => {
      calls.push('test')
      return [200, page.dataSources[0]]
    })

    const allowed = await mountComponent(page, {
      beforeTest: async () => {
        calls.push('save')
        return true
      },
    })
    await allowed.find('button').trigger('click')
    await flushPromises()
    expect(calls).toEqual(['save', 'test'])

    calls.length = 0
    const refused = await mountComponent(page, {
      beforeTest: async () => false,
    })
    await refused.find('button').trigger('click')
    await flushPromises()
    expect(calls).toEqual([])
  })

  test('shows the error of a failed save before the test', async () => {
    const page = createPage(null)
    const wrapper = await mountComponent(page, {
      beforeTest: () =>
        Promise.reject({ response: { data: { detail: 'Invalid timeout.' } } }),
    })
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.data-source-test-form__code').text()).toBe(
      'Invalid timeout.'
    )
  })

  test('shows a shared test without a button of its own', async () => {
    const page = createPage(null)
    const dataSourceTest = reactive({
      isLoading: false,
      error: null,
      hasSampleData: true,
      sampleData: [{ id: 1 }],
      test: vi.fn(),
    })

    const wrapper = await mountComponent(
      page,
      { showButton: false },
      { dataSourceTest }
    )

    expect(wrapper.text()).not.toContain('dataSourceTestForm.buttonLabel')
    expect(
      JSON.parse(wrapper.find('.data-source-test-form__code').text())
    ).toEqual([{ id: 1 }])
  })
})
