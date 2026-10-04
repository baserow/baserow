import { TestApp } from '@baserow/test/helpers/testApp'
import FieldForm from '@baserow/modules/database/components/field/FieldForm'

describe('FieldForm field type dropdown', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
    vi.restoreAllMocks()
  })

  // Shallow: the real Dropdown registers a MutationObserver on a ref that
  // happy-dom never populates, and the type list is all this asserts on.
  const mountForm = async (defaultValues = {}) =>
    testApp.mount(FieldForm, {
      shallow: true,
      propsData: {
        table: { id: 1 },
        view: null,
        primary: false,
        allFieldsInTable: [{ id: 1, type: 'text', name: 'Name' }],
        database: { id: 1, workspace: { id: 1 } },
        defaultValues,
      },
    })

  const hideButtonType = () => {
    const buttonFieldType = testApp._app.$registry.get('field', 'button')
    vi.spyOn(buttonFieldType, 'isVisibleInDropdown').mockReturnValue(false)
  }

  test('a hidden field type is not listed when creating a field', async () => {
    hideButtonType()
    const wrapper = await mountForm()
    expect(Object.keys(wrapper.vm.fieldTypes)).not.toContain('button')
  })

  test('a visible field type is listed', async () => {
    const wrapper = await mountForm()
    expect(Object.keys(wrapper.vm.fieldTypes)).toContain('button')
  })

  test('a hidden field type is still listed while editing a field of that type', async () => {
    // Otherwise the dropdown has no item matching its own value and renders
    // blank. The button type is only a stand-in for any hidden type here.
    hideButtonType()
    const wrapper = await mountForm({ id: 5, type: 'button', label: 'Open' })
    expect(Object.keys(wrapper.vm.fieldTypes)).toContain('button')
  })
})

describe('FieldForm vector search option', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountForm = async (defaultValues = {}) =>
    testApp.mount(FieldForm, {
      shallow: true,
      propsData: {
        table: { id: 1 },
        view: null,
        primary: false,
        allFieldsInTable: [{ id: 1, type: 'text', name: 'Name' }],
        database: { id: 1, workspace: { id: 1 } },
        defaultValues,
      },
    })

  test('only long text fields on a configured instance can enable it', async () => {
    const wrapper = await mountForm({ type: 'long_text' })
    expect(wrapper.vm.canHaveVectorSearch).toBe(true)
    expect(wrapper.vm.vectorSearchAvailable).toBe(false)

    testApp.store.commit('settings/UPDATE_SETTINGS', {
      vector_search_available: true,
    })
    expect(wrapper.vm.vectorSearchAvailable).toBe(true)

    wrapper.vm.values = { ...wrapper.vm.values, vector_search_enabled: true }
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.getFormValues().vector_search_enabled).toBe(true)

    // Switching to a type without vector search drops the flag on submit.
    wrapper.vm.values = { ...wrapper.vm.values, type: 'text' }
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.canHaveVectorSearch).toBe(false)
    expect(wrapper.vm.getFormValues().vector_search_enabled).toBe(false)
  })
})
