import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import CreateWidgetModal from '@baserow/modules/dashboard/components/CreateWidgetModal'

const UpgradeModal = {
  ...ModalStub,
  name: 'UpgradeModal',
  template: '<div v-if="open" class="upgrade-modal">Upgrade</div>',
}

describe('CreateWidgetModal', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  async function mountModal({ loading = false, chartAvailable = true } = {}) {
    const chartType = {
      name: 'Chart',
      isFilterWidget: false,
      isAvailable: () => chartAvailable,
      getDeactivatedModal: () => [UpgradeModal, {}],
    }
    const filterType = {
      name: 'Text filter',
      isFilterWidget: true,
      isAvailable: () => true,
      getDeactivatedModal: () => null,
    }
    chartType.variations = ['Bar chart', 'Line chart'].map((name) => ({
      name,
      createWidgetImage: '',
      type: chartType,
      params: {
        default_series_chart_type: name === 'Bar chart' ? 'BAR' : 'LINE',
      },
    }))
    filterType.variations = [
      {
        name: 'Text filter',
        createWidgetImage: '',
        type: filterType,
        params: {},
      },
    ]
    const registry = testApp.getRegistry()
    const getOrderedList = registry.getOrderedList.bind(registry)
    vi.spyOn(registry, 'getOrderedList').mockImplementation((name) =>
      name === 'dashboardWidget'
        ? [chartType, filterType]
        : getOrderedList(name)
    )
    const wrapper = await testApp.mount(CreateWidgetModal, {
      props: { dashboard: { workspace: { id: 1 } }, loading },
      global: { stubs: { Modal: ModalStub } },
    })
    await wrapper.vm.show()
    await flushPromises()
    return { wrapper, chartType }
  }

  test('groups widgets and filters, searches variations and preserves selection parameters', async () => {
    const { wrapper, chartType } = await mountModal()

    expect(
      wrapper.findAll('.item-picker-modal__group-title').map((el) => el.text())
    ).toEqual(['createWidgetModal.widgets', 'createWidgetModal.filters'])
    expect(wrapper.findAll('.item-picker-card')).toHaveLength(3)

    await wrapper.get('input').setValue('line')
    expect(wrapper.findAll('.item-picker-card')).toHaveLength(1)
    expect(wrapper.get('.item-picker-card').text()).toBe('Line chart')

    await wrapper.get('.item-picker-card').trigger('click')
    expect(wrapper.emitted('widget-variation-selected')).toEqual([
      [chartType.variations[1]],
    ])
    expect(wrapper.find('.item-picker-card').exists()).toBe(false)
  })

  test('prevents selection while widget creation is pending', async () => {
    const { wrapper } = await mountModal({ loading: true })

    for (const card of wrapper.findAll('.item-picker-card')) {
      expect(card.attributes('disabled')).toBeDefined()
      await card.trigger('click')
    }

    expect(wrapper.emitted('widget-variation-selected')).toBeUndefined()
    expect(wrapper.findAll('.item-picker-card')).toHaveLength(3)
  })

  test('opens the upgrade modal for locked widgets without selecting or closing the picker', async () => {
    const { wrapper } = await mountModal({ chartAvailable: false })

    const card = wrapper.findAll('.item-picker-card')[0]
    expect(card.find('.iconoir-lock').exists()).toBe(true)
    await card.trigger('click')

    expect(wrapper.get('.upgrade-modal').text()).toBe('Upgrade')
    expect(wrapper.emitted('widget-variation-selected')).toBeUndefined()
    expect(wrapper.findAll('.item-picker-card')).toHaveLength(3)
  })
})
