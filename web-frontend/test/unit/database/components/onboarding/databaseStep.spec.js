import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import DatabaseStep from '@baserow/modules/database/components/onboarding/DatabaseStep'

describe('DatabaseStep', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const renderOnServer = () => {
    const app = createSSRApp(DatabaseStep, { data: {} })
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: {} } }))
    app.use(testApp.store)
    // The onboarding step components are globally registered by Nuxt, and are not
    // resolvable in the bare app the server renderer needs.
    app.config.warnHandler = () => {}
    Object.assign(app.config.globalProperties, {
      $registry: testApp.$registry,
      $t: (key) => key,
    })
    return renderToString(app)
  }

  test('renders the database name input server-side', async () => {
    const html = await renderOnServer()

    expect(html).toContain('databaseStep.databaseNameLabel')
  })

  test('shows a required error when the database name is cleared', async () => {
    const wrapper = await testApp.mount(DatabaseStep, {
      propsData: { data: {} },
    })

    await wrapper.find('input').setValue('')
    await flushPromises()

    expect(wrapper.find('.control__messages--error').text()).toBe(
      'error.requiredField'
    )
  })
})
