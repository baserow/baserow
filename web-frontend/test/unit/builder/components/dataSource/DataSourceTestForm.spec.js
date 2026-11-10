import { vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import MockAdapter from 'axios-mock-adapter'

import DataSourceTestForm from '@baserow/modules/builder/components/dataSource/DataSourceTestForm'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

const SampleDataViewerStub = {
  name: 'SampleDataViewer',
  props: {
    sampleData: { type: [Object, Array, String], default: null },
    isError: { type: Boolean, default: false },
    modalTitle: { type: String, default: '' },
    modalSubtitle: { type: String, default: '' },
  },
  template:
    '<div class="sample-data-viewer" :class="{ \'sample-data-viewer--error\': isError }">{{ JSON.stringify(sampleData) }}</div>',
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

  const mountComponent = (page) =>
    mountSuspended(DataSourceTestForm, {
      props: { dataSource: page.dataSources[0], page },
      global: {
        provide: { applicationContext: { builder: { id: 1 } } },
        stubs: { SampleDataViewer: SampleDataViewerStub },
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

    expect(wrapper.find('.sample-data-viewer').exists()).toBe(false)
    expect(wrapper.text()).toContain('dataSourceTestForm.testDescription')
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

    const viewer = wrapper.find('.sample-data-viewer')
    expect(viewer.text()).toBe('{"name":"Lamp"}')
    expect(viewer.classes()).not.toContain('sample-data-viewer--error')
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

    const viewer = wrapper.find('.sample-data-viewer')
    expect(viewer.text()).toBe('"Row 999 does not exist."')
    expect(viewer.classes()).toContain('sample-data-viewer--error')
  })
})
