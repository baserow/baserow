import { mountSuspended } from '@nuxt/test-utils/runtime'
import CollectionElementHeader from '@baserow/modules/builder/components/elements/components/CollectionElementHeader.vue'

const SearchHeader = {
  props: ['searchableProperties', 'sortableProperties', 'filterableProperties'],
  emits: ['search-changed'],
  template:
    "<button @click=\"$emit('search-changed', 'Task')\">Search</button>",
}

/** Mount the header with schema and registry boundaries supplied by its parent. */
function mountHeader(searchableProperties) {
  const dataSource = { id: 1, type: 'list_rows' }
  const elementType = {
    adhocSortableProperties: () => [],
    adhocFilterableProperties: () => [],
    adhocSearchableProperties: () => searchableProperties,
  }
  return mountSuspended(CollectionElementHeader, {
    props: { element: { type: 'repeat', data_source_id: 1 } },
    global: {
      provide: { builder: {}, currentPage: {} },
      mocks: {
        $store: {
          getters: {
            'page/getSharedPage': () => null,
            'dataSource/getPagesDataSourceById': () => dataSource,
          },
        },
        $registry: {
          get: (namespace) =>
            namespace === 'element'
              ? elementType
              : { adhocHeaderComponent: SearchHeader },
        },
      },
    },
  })
}

describe('CollectionElementHeader', () => {
  test('does not mount refinement UI when every capability is disabled', async () => {
    const wrapper = await mountHeader([])
    expect(wrapper.html()).toMatchSnapshot()
    wrapper.unmount()
  })

  test('renders enabled refinements and forwards their search event', async () => {
    const wrapper = await mountHeader([{ type: 'string', title: 'Name' }])
    expect(wrapper.html()).toMatchSnapshot()
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('search-changed')).toEqual([['Task']])
    wrapper.unmount()
  })
})
