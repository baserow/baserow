import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'

import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'

// Items only register with their dropdown once mounted, which never happens on
// the server. The selected value must nevertheless be part of the rendered HTML.
describe('Dropdown server side rendering', () => {
  const render = async (props) => {
    const app = createSSRApp({
      render: () =>
        h(Dropdown, props, {
          default: () => [
            h(DropdownItem, { value: 'created', name: 'Created' }),
            h(DropdownItem, { value: 'last_viewed', name: 'Last viewed' }),
          ],
        }),
    })
    app.config.globalProperties.$t = (key) => key
    // Globally registered in the app, irrelevant for the selected value.
    app.component('Checkbox', { render: () => null })
    app.directive('auto-overflow-scroll', {})
    app.directive('tooltip', {})
    return await renderToString(app)
  }

  test('renders the name of the selected item', async () => {
    const html = await render({ modelValue: 'last_viewed', showSearch: false })
    expect(html).toContain('dropdown__selected-text')
    expect(html).toContain('Last viewed')
    expect(html).not.toContain('dropdown__selected-placeholder')
  })

  test('renders the placeholder without a matching item', async () => {
    const html = await render({ modelValue: 'unknown', showSearch: false })
    expect(html).toContain('dropdown__selected-placeholder')
  })

  test('renders every selected name of a multiple dropdown', async () => {
    const html = await render({
      modelValue: ['created', 'last_viewed'],
      multiple: true,
      showSearch: false,
    })
    expect(html).toContain('Created, Last viewed')
  })
})
