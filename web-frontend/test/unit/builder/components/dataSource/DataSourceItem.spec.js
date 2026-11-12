import { mountSuspended } from '@nuxt/test-utils/runtime'

import DataSourceItem from '@baserow/modules/builder/components/dataSource/DataSourceItem'
import httpRequestImage from '@baserow/modules/integrations/core/assets/images/httpRequest.svg?url'

const mountComponent = (dataSource) =>
  mountSuspended(DataSourceItem, {
    props: { dataSource },
    global: {
      provide: { workspace: { id: 1 }, builder: { id: 1 } },
      stubs: { DataSourceItemContext: true },
      mocks: { $hasPermission: () => true },
    },
  })

describe('DataSourceItem', () => {
  test('shows a data source without an integration with its own image', async () => {
    const wrapper = await mountComponent({
      id: 1,
      name: 'Products',
      type: 'http_get',
      url: { formula: "'https://example.test'" },
      schema: { type: 'object', properties: {} },
    })

    const image = wrapper.find('.avatar__image')
    expect(image.exists()).toBe(true)
    expect(image.attributes('src')).toBe(httpRequestImage)
    expect(wrapper.find('.avatar__icon').exists()).toBe(false)
  })

  test('shows a data source in error with the error icon', async () => {
    const wrapper = await mountComponent({
      id: 1,
      name: 'Products',
      type: 'http_get',
      url: { formula: '' },
    })

    expect(wrapper.find('.avatar__image').exists()).toBe(false)
    expect(wrapper.find('.avatar__icon').classes()).toContain(
      'iconoir-warning-circle'
    )
  })
})
