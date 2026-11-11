import { mountSuspended } from '@nuxt/test-utils/runtime'
import { nextTick, reactive } from 'vue'

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
})
