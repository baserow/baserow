import { mountSuspended } from '@nuxt/test-utils/runtime'
import { nextTick, reactive } from 'vue'
import { vi } from 'vitest'

import PageEditorContent from '@baserow/modules/builder/components/PageEditorContent'

const mountEditor = async (page) => {
  const sharedPage = {
    id: 2,
    shared: true,
    _: { dataSourceLoading: false, dataSourceFetched: true },
    dataSources: [],
  }
  const builder = {
    id: 1,
    pages: [sharedPage, page],
    theme: {},
  }

  return await mountSuspended(PageEditorContent, {
    props: {
      workspace: { id: 1 },
      builder,
      page,
      loading: false,
    },
    global: {
      stubs: {
        PageHeader: true,
        PagePreview: {
          inject: ['applicationContext'],
          template:
            '<div data-test-id="page-preview">{{ applicationContext.dataScope.includeTargetElement }}</div>',
        },
        PageSidePanels: true,
        SkeletonBlock: true,
      },
    },
  })
}

describe('PageEditorContent', () => {
  test('waits for data sources before rendering the page preview', async () => {
    const page = reactive({
      id: 1,
      _: { dataSourceLoading: true, dataSourceFetched: false },
      dataSources: [],
    })

    const wrapper = await mountEditor(page)

    expect(wrapper.find('[data-test-id="page-preview"]').exists()).toBe(false)

    page._.dataSourceLoading = false
    page._.dataSourceFetched = true
    await nextTick()

    expect(wrapper.find('[data-test-id="page-preview"]').exists()).toBe(true)
    expect(wrapper.find('[data-test-id="page-preview"]').text()).toBe('false')
    wrapper.unmount()
  })

  test('keeps the page preview mounted while data sources change', async () => {
    const page = reactive({
      id: 1,
      _: { dataSourceLoading: false, dataSourceFetched: true },
      dataSources: [],
    })

    const wrapper = await mountEditor(page)
    const preview = wrapper.find('[data-test-id="page-preview"]')
    expect(preview.exists()).toBe(true)

    // Creating, updating or moving a data source toggles the loading flag.
    page._.dataSourceLoading = true
    await nextTick()

    expect(wrapper.find('[data-test-id="page-preview"]').element).toBe(
      preview.element
    )
    wrapper.unmount()
  })

  test('fetches the content again when a data source changes, not when it is tested', async () => {
    const dataSource = {
      id: 1,
      type: 'http_get',
      url: { formula: "'https://a.test'" },
      schema: null,
      sample_data: null,
    }
    const page = reactive({
      id: 1,
      _: { dataSourceLoading: false, dataSourceFetched: true },
      dataSources: [dataSource],
    })
    const fetchAction = 'dataSourceContent/debouncedFetchPageDataSourceContent'
    const { $store } = useNuxtApp()
    const originalDispatch = $store.dispatch.bind($store)
    // The fetch itself is left out: it would send a request once the test is
    // over.
    const dispatch = vi
      .spyOn($store, 'dispatch')
      .mockImplementation((action, ...args) =>
        action === fetchAction ? undefined : originalDispatch(action, ...args)
      )
    const fetchCalls = () =>
      dispatch.mock.calls.filter(([action]) => action === fetchAction).length

    const wrapper = await mountEditor(page)
    const callsAfterMount = fetchCalls()

    // A test stores the sample data and the schema built from it.
    page.dataSources[0].sample_data = { data: { name: 'Ada' } }
    page.dataSources[0].schema = { type: 'object', properties: {} }
    await nextTick()
    expect(fetchCalls()).toBe(callsAfterMount)

    page.dataSources[0].url.formula = "'https://b.test'"
    await nextTick()
    expect(fetchCalls()).toBe(callsAfterMount + 1)

    dispatch.mockRestore()
    wrapper.unmount()
  })
})
