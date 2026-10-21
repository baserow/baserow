import { defineComponent } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import SemanticSearchFieldSetting from '@baserow_enterprise/components/semanticSearch/SemanticSearchFieldSetting'

const PaidFeaturesModalStub = defineComponent({
  name: 'PaidFeaturesModal',
  data() {
    return { shown: false }
  },
  methods: {
    show() {
      this.shown = true
    },
  },
  template: '<div v-if="shown" class="paid-features-modal-stub"></div>',
})

describe('SemanticSearchFieldSetting', () => {
  let testApp = null

  const workspace = { id: 1, name: 'Workspace' }
  const database = { id: 1, workspace }

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available: true },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const giveAdvancedLicense = () => {
    testApp.store.dispatch('auth/forceUpdateUserData', {
      active_licenses: { instance_wide: { advanced: true } },
    })
  }

  const mountComponent = (fieldValues, defaultValues = {}) =>
    testApp.mount(SemanticSearchFieldSetting, {
      props: {
        fieldValues,
        defaultValues,
        database,
        table: { id: 1 },
      },
      global: { stubs: { PaidFeaturesModal: PaidFeaturesModalStub } },
    })

  test('can be enabled with the advanced license', async () => {
    giveAdvancedLicense()
    const wrapper = await mountComponent({ type: 'long_text' })

    expect(wrapper.find('.iconoir-lock').exists()).toBe(false)
    await wrapper.find('.switch').trigger('click')

    expect(wrapper.find('.switch').classes()).toContain('switch--active')
    expect(wrapper.find('.paid-features-modal-stub').exists()).toBe(false)
  })

  test('opens the paywall without the license', async () => {
    const wrapper = await mountComponent({ type: 'text' })

    expect(wrapper.find('.iconoir-lock').exists()).toBe(true)
    await wrapper.find('.switch').trigger('click')

    expect(wrapper.find('.switch').classes()).not.toContain('switch--active')
    expect(wrapper.find('.paid-features-modal-stub').exists()).toBe(true)
  })

  test('can be disabled without the license', async () => {
    const wrapper = await mountComponent(
      { type: 'text' },
      { semantic_search_enabled: true, semantic_search_status: 'paused' }
    )

    expect(wrapper.text()).toContain('semanticSearchFieldSetting.statusPaused')
    await wrapper.find('.switch').trigger('click')

    expect(wrapper.find('.switch').classes()).not.toContain('switch--active')
    expect(wrapper.find('.paid-features-modal-stub').exists()).toBe(false)
  })

  test('is disabled for incompatible fields', async () => {
    giveAdvancedLicense()
    const wrapper = await mountComponent({
      type: 'formula',
      formula_type: 'number',
    })

    expect(wrapper.find('.switch').classes()).toContain('switch--disabled')
  })

  test('is disabled when the instance has no embeddings service', async () => {
    giveAdvancedLicense()
    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available: false },
    })
    const wrapper = await mountComponent({ type: 'text' })

    expect(wrapper.find('.switch').classes()).toContain('switch--disabled')
  })

  test('can be disabled when the instance has no embeddings service', async () => {
    giveAdvancedLicense()
    testApp.store.commit('settings/SET_SETTINGS', {
      semantic_search: { available: false },
    })
    const wrapper = await mountComponent(
      { type: 'text' },
      { semantic_search_enabled: true, semantic_search_status: 'unavailable' }
    )

    expect(wrapper.text()).toContain(
      'semanticSearchFieldSetting.statusUnavailable'
    )
    await wrapper.find('.switch').trigger('click')

    expect(wrapper.find('.switch').classes()).not.toContain('switch--active')
    expect(wrapper.vm.getFormValues()).toEqual({
      semantic_search_enabled: false,
    })
  })

  test('shows the indexing status with a loading animation', async () => {
    giveAdvancedLicense()
    const wrapper = await mountComponent(
      { type: 'text' },
      { semantic_search_enabled: true, semantic_search_status: 'indexing' }
    )

    const updating = wrapper.find('.semantic-search-field-setting__updating')
    expect(updating.text()).toBe('semanticSearchFieldSetting.indexing')
    expect(
      updating.find('.semantic-search-field-setting__spinner').exists()
    ).toBe(true)
  })

  test('shows nothing when the index is ready', async () => {
    giveAdvancedLicense()
    const wrapper = await mountComponent(
      { type: 'text' },
      { semantic_search_enabled: true, semantic_search_status: 'ready' }
    )

    expect(wrapper.text()).not.toContain('semanticSearchFieldSetting.status')
    expect(wrapper.find('.loading').exists()).toBe(false)
  })
})
