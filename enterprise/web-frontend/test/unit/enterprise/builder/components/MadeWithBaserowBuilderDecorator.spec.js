import {
  mount,
  renderToString,
  flushPromises,
  enableAutoUnmount,
} from '@vue/test-utils'
import { vi } from 'vitest'
import { reactive } from 'vue'
import MadeWithBaserowBuilderDecorator from '@baserow_enterprise/components/builder/MadeWithBaserowBuilderDecorator'

enableAutoUnmount(afterEach)

function createStore({ publicDomain, settingsLoaded, settings }) {
  const store = {
    getters: reactive({
      'publicBuilder/getPublicDomain': publicDomain,
      'settings/isLoaded': settingsLoaded,
      'settings/get': settings,
    }),
    dispatch: vi.fn(() => {
      store.getters['settings/isLoaded'] = true
      return Promise.resolve()
    }),
  }
  return store
}

function decoratorOptions({
  publicDomain = 'phishing.example.com',
  settingsLoaded = true,
  settings = {},
  showPaidFeaturesModal = false,
} = {}) {
  const store = createStore({ publicDomain, settingsLoaded, settings })
  const options = {
    props: { showPaidFeaturesModal },
    global: {
      mocks: {
        $t: (key) => key,
        $store: store,
      },
      stubs: {
        PaidFeaturesModal: {
          methods: { show: vi.fn() },
          template: '<div data-testid="paid-features-modal"></div>',
        },
        ReportAbuseModal: {
          props: ['resourceType', 'identifier'],
          data() {
            return { shown: false }
          },
          methods: {
            show() {
              this.shown = true
            },
          },
          template: `
            <div
              data-testid="report-abuse-modal"
              :data-shown="shown"
              :data-resource-type="resourceType"
              :data-identifier="identifier"
            ></div>
          `,
        },
      },
    },
  }
  return { options, store }
}

function mountDecorator(params) {
  const { options, store } = decoratorOptions(params)
  return { wrapper: mount(MadeWithBaserowBuilderDecorator, options), store }
}

describe('MadeWithBaserowBuilderDecorator', () => {
  test('shows the report abuse link next to the badge on a published site', async () => {
    const { wrapper } = mountDecorator()

    const link = wrapper.get('.made-with-baserow__report-abuse')
    expect(link.text()).toBe('madeWithBaserow.reportAbuse')

    await link.trigger('click')

    const modal = wrapper.get('[data-testid="report-abuse-modal"]')
    expect(modal.attributes('data-shown')).toBe('true')
    expect(modal.attributes('data-resource-type')).toBe('builder')
    expect(modal.attributes('data-identifier')).toBe('phishing.example.com')
  })

  test('hides the report abuse link when reporting is disabled', () => {
    const { wrapper } = mountDecorator({
      settings: { allow_reporting_abuse: false },
    })

    expect(wrapper.find('.made-with-baserow').exists()).toBe(true)
    expect(wrapper.find('.made-with-baserow__report-abuse').exists()).toBe(
      false
    )
    expect(wrapper.find('[data-testid="report-abuse-modal"]').exists()).toBe(
      false
    )
  })

  test('hides the report abuse link without a public domain', () => {
    const { wrapper, store } = mountDecorator({
      publicDomain: null,
      settingsLoaded: false,
    })

    expect(wrapper.find('.made-with-baserow__report-abuse').exists()).toBe(
      false
    )
    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('hides the report abuse link in the editor', () => {
    const { wrapper, store } = mountDecorator({
      showPaidFeaturesModal: true,
      settingsLoaded: false,
    })

    expect(wrapper.find('.made-with-baserow__report-abuse').exists()).toBe(
      false
    )
    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('loads the settings in the browser when they are missing', async () => {
    const { wrapper, store } = mountDecorator({ settingsLoaded: false })

    expect(store.dispatch).toHaveBeenCalledWith('settings/load')
    await flushPromises()
    expect(wrapper.find('.made-with-baserow__report-abuse').exists()).toBe(true)
  })

  test('renders the report abuse link on the server', async () => {
    const { options, store } = decoratorOptions({ settingsLoaded: false })

    const html = await renderToString(MadeWithBaserowBuilderDecorator, options)

    expect(store.dispatch).toHaveBeenCalledWith('settings/load')
    expect(html).toContain('madeWithBaserow.reportAbuse')
  })

  test('does not load the settings on the server without a public domain', async () => {
    const { options, store } = decoratorOptions({
      publicDomain: null,
      settingsLoaded: false,
    })

    const html = await renderToString(MadeWithBaserowBuilderDecorator, options)

    expect(store.dispatch).not.toHaveBeenCalled()
    expect(html).not.toContain('madeWithBaserow.reportAbuse')
  })
})
