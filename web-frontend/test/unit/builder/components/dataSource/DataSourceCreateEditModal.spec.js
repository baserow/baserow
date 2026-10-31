import { defineComponent } from 'vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'

import DataSourceCreateEditModal from '@baserow/modules/builder/components/dataSource/DataSourceCreateEditModal'
import { ELEMENT_EVENTS } from '@baserow/modules/builder/enums'

const DataSourceFormStub = defineComponent({
  name: 'DataSourceForm',
  emits: ['saved'],
  template: '<div class="data-source-form-stub" />',
})

const builder = { id: 1, workspace: { id: 1 } }
const currentPage = { id: 1 }
const sharedPage = { id: 2 }
const dataSource = { id: 3, page_id: 1, type: 'http_get' }
const elements = {
  1: [{ id: 10, page_id: 1 }],
  2: [{ id: 20, page_id: 2 }],
}

async function mountComponent(dispatch) {
  return await mountSuspended(DataSourceCreateEditModal, {
    props: { dataSourceId: dataSource.id },
    global: {
      provide: { builder, currentPage },
      stubs: {
        Modal: { template: '<div><slot /></div>' },
        DataSourceForm: DataSourceFormStub,
        Error: true,
        Alert: true,
        Button: true,
        ButtonText: true,
      },
      mocks: {
        $store: {
          getters: {
            'dataSource/getPageDataSources': (page) =>
              page.id === currentPage.id ? [dataSource] : [],
            'page/getSharedPage': () => sharedPage,
            'page/getById': () => currentPage,
            'integration/getIntegrations': () => [],
            'element/getElementsOrdered': (page) => elements[page.id],
          },
          dispatch,
        },
        $t: (key) => key,
      },
    },
  })
}

describe('DataSourceCreateEditModal', () => {
  test('the elements fetch the data source again when a test saved it', async () => {
    const dispatch = vi.fn().mockResolvedValue({})
    const wrapper = await mountComponent(dispatch)

    wrapper.findComponent(DataSourceFormStub).vm.$emit('saved')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith('element/emitElementEvent', {
      event: ELEMENT_EVENTS.DATA_SOURCE_AFTER_UPDATE,
      elements: [...elements[1], ...elements[2]],
      dataSourceId: dataSource.id,
      builder,
    })
  })
})
