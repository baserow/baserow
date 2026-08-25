import flushPromises from 'flush-promises'

import { TestApp } from '@baserow/test/helpers/testApp'
import CopyViewConfigurationModal from '@baserow/modules/database/components/view/CopyViewConfigurationModal'

describe('CopyViewConfigurationModal', () => {
  let testApp = null

  const database = { id: 1, workspace: { id: 1 } }
  const destViewId = 2
  const galleryViewId = 3

  beforeEach(() => {
    testApp = new TestApp()

    const baseValues = {
      table_id: 10,
      filter_type: 'AND',
      filters_disabled: false,
    }
    testApp.store.dispatch('view/forceCreate', {
      data: { id: 1, type: 'grid', name: 'Source grid', ...baseValues },
    })
    testApp.store.dispatch('view/forceCreate', {
      data: {
        id: destViewId,
        type: 'grid',
        name: 'Destination',
        ...baseValues,
      },
    })
    testApp.store.dispatch('view/forceCreate', {
      data: {
        id: galleryViewId,
        type: 'gallery',
        name: 'Gallery',
        ...baseValues,
      },
    })
    testApp.store.dispatch('view/forceCreate', {
      data: { id: 4, type: 'form', name: 'Form', ...baseValues },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountModal = async (viewId = destViewId) => {
    const destView = testApp.store.getters['view/get'](viewId)
    const wrapper = await testApp.mount(CopyViewConfigurationModal, {
      propsData: { view: destView, database },
    })
    return wrapper
  }

  // The test environment resolves every i18n key to itself, so the switch
  // labels are the raw `copyViewConfigurationOption.*` keys here.
  const label = (name) => `copyViewConfigurationOption.${name}`

  // The teleported modal element is replaced on re-render, so it must be
  // fetched freshly for every assertion.
  const element = (wrapper) => wrapper.vm.getTeleportedElement()
  const getSwitches = (wrapper) => [
    ...element(wrapper).querySelectorAll('.switch'),
  ]
  const switchLabels = (wrapper) =>
    getSwitches(wrapper).map((s) => s.textContent.trim())
  const activeSwitchLabels = (wrapper) =>
    getSwitches(wrapper)
      .filter((s) => s.classList.contains('switch--active'))
      .map((s) => s.textContent.trim())
  const disabledSwitchLabels = (wrapper) =>
    getSwitches(wrapper)
      .filter((s) => s.classList.contains('switch--disabled'))
      .map((s) => s.textContent.trim())
  const getCopyButton = (wrapper) => {
    const buttons = [...element(wrapper).querySelectorAll('button')]
    return buttons[buttons.length - 1]
  }

  const selectSourceView = async (wrapper, name) => {
    const item = [...element(wrapper).querySelectorAll('.select__item a')].find(
      (a) => a.textContent.includes(name)
    )
    item.click()
    await flushPromises()
  }

  test('the dropdown excludes the destination view and form views', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show()
    await flushPromises()

    const names = [
      ...element(wrapper).querySelectorAll('.select__item-name-text'),
    ].map((node) => node.textContent.trim())
    expect(names).toEqual(['Source grid', 'Gallery'])
  })

  test('a grid destination renders every option of the view type', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show()
    await flushPromises()

    expect(switchLabels(wrapper)).toEqual([
      label('fieldVisibility'),
      label('fieldOrder'),
      label('fieldWidths'),
      label('viewSettings'),
      label('filters'),
      label('sorts'),
      label('groupBys'),
      label('decorations'),
      label('defaultRowValues'),
    ])
  })

  test('a gallery destination does not render the grid specific options', async () => {
    const wrapper = await mountModal(galleryViewId)
    wrapper.vm.show()
    await flushPromises()

    expect(switchLabels(wrapper)).toEqual([
      label('fieldVisibility'),
      label('fieldOrder'),
      label('filters'),
      label('sorts'),
      label('decorations'),
      label('defaultRowValues'),
    ])
  })

  test('only the initial selection is checked after picking a source view', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show(['filters'])
    await flushPromises()

    expect(activeSwitchLabels(wrapper)).toEqual([])

    await selectSourceView(wrapper, 'Source grid')
    expect(activeSwitchLabels(wrapper)).toEqual([label('filters')])
  })

  test('all enabled options are checked when shown without initial selection', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show()
    await flushPromises()

    await selectSourceView(wrapper, 'Gallery')

    // The gallery source doesn't support column widths, row height and
    // groups, and the premium decorators are deactivated without a license,
    // so those switches stay disabled and unchecked.
    expect(activeSwitchLabels(wrapper)).toEqual([
      label('fieldVisibility'),
      label('fieldOrder'),
      label('filters'),
      label('sorts'),
      label('defaultRowValues'),
    ])
    expect(disabledSwitchLabels(wrapper)).toEqual([
      label('fieldWidths'),
      label('viewSettings'),
      label('groupBys'),
      label('decorations'),
    ])
  })

  test('select all and clear all toggle the enabled switches', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show(['filters'])
    await flushPromises()

    await selectSourceView(wrapper, 'Source grid')

    expect(getCopyButton(wrapper).disabled).toBe(false)

    const [selectAllButton] = [...element(wrapper).querySelectorAll('button')]
    selectAllButton.click()
    await flushPromises()
    expect(activeSwitchLabels(wrapper)).toEqual([
      label('fieldVisibility'),
      label('fieldOrder'),
      label('fieldWidths'),
      label('viewSettings'),
      label('filters'),
      label('sorts'),
      label('groupBys'),
      label('defaultRowValues'),
    ])

    const clearAllButton = [...element(wrapper).querySelectorAll('button')][1]
    clearAllButton.click()
    await flushPromises()
    expect(activeSwitchLabels(wrapper)).toEqual([])
    expect(getCopyButton(wrapper).disabled).toBe(true)
  })

  test('the copy button is disabled until a source view is selected', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show()
    await flushPromises()

    expect(getCopyButton(wrapper).disabled).toBe(true)

    await selectSourceView(wrapper, 'Source grid')
    expect(getCopyButton(wrapper).disabled).toBe(false)
  })

  test('submitting disables the modal and hides it on success', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show(['filters'])
    await flushPromises()

    await selectSourceView(wrapper, 'Source grid')

    let resolveRequest
    testApp.mockServer.mock
      .onPost(`/database/views/${destViewId}/copy-configuration/`)
      .reply(() => {
        return new Promise((resolve) => {
          resolveRequest = () =>
            resolve([
              200,
              {
                id: destViewId,
                table_id: 10,
                filter_type: 'AND',
                filters: [],
                filter_groups: [],
                sortings: [],
                group_bys: [],
                decorations: [],
              },
            ])
        })
      })

    getCopyButton(wrapper).click()
    await flushPromises()

    // While the request is pending, the whole modal is in a loading state.
    expect(wrapper.vm.loading).toBe(true)
    expect(getCopyButton(wrapper).disabled).toBe(true)
    expect(disabledSwitchLabels(wrapper).length).toBe(9)

    resolveRequest()
    await flushPromises()

    expect(wrapper.vm.loading).toBe(false)
    expect(wrapper.vm.$refs.modal.open).toBe(false)
  })

  test('a failing request shows the error and keeps the modal open', async () => {
    const wrapper = await mountModal()
    wrapper.vm.show(['filters'])
    await flushPromises()

    await selectSourceView(wrapper, 'Source grid')

    testApp.mockServer.mock
      .onPost(`/database/views/${destViewId}/copy-configuration/`)
      .reply(400, {
        error: 'ERROR_VIEW_CONFIGURATION_COPY_CATEGORY_NOT_SUPPORTED',
        detail: '',
      })

    getCopyButton(wrapper).click()
    await flushPromises()

    expect(wrapper.vm.loading).toBe(false)
    expect(wrapper.vm.$refs.modal.open).toBe(true)
    expect(wrapper.vm.error.visible).toBe(true)
  })
})
