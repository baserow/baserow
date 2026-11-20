import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { vi } from 'vitest'

import DataSourceContext from '@baserow/modules/builder/components/page/header/DataSourceContext'

const ContextStub = defineComponent({
  name: 'Context',
  emits: ['shown'],
  template: '<div><slot /></div>',
})

describe('DataSourceContext', () => {
  test('fetches every integration the builder can use when it opens', async () => {
    // The workspace ones too, so the data source form offers the tables as
    // they are now: no realtime event about the integration tells the store.
    const builder = { id: 1 }
    const store = {
      dispatch: vi.fn().mockResolvedValue([]),
      getters: {
        'dataSource/getPageDataSources': () => [],
        'page/getSharedPage': () => ({ id: 2 }),
        'integration/getIntegrations': () => [],
      },
    }

    const wrapper = await mountSuspended(DataSourceContext, {
      props: { page: { id: 3 } },
      global: {
        provide: { builder, workspace: { id: 4 } },
        stubs: {
          Context: ContextStub,
          DataSourceCreateEditModal: true,
        },
        mocks: {
          $store: store,
          $t: (key) => key,
          $hasPermission: () => false,
        },
      },
    })
    wrapper.findComponent(ContextStub).vm.$emit('shown')
    await flushPromises()

    expect(store.dispatch).toHaveBeenCalledWith('integration/fetchUsable', {
      application: builder,
    })
    expect(store.dispatch).not.toHaveBeenCalledWith(
      'integration/fetch',
      expect.anything()
    )
    wrapper.unmount()
  })
})
