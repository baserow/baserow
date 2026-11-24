import { mount } from '@vue/test-utils'

import CreateWidgetCard from '@baserow/modules/dashboard/components/CreateWidgetCard'

const tooltip = { mounted: vi.fn() }

const widgetType = {
  isAvailable: () => true,
  getDeactivatedModal: () => null,
}

function mountCreateWidgetCard(disabled) {
  return mount(CreateWidgetCard, {
    global: { directives: { tooltip } },
    props: {
      dashboard: { workspace: { id: 1 } },
      widgetType,
      variation: {
        name: 'Summary',
        description: 'A single number',
        createWidgetImage: '',
      },
      disabled,
    },
  })
}

describe('CreateWidgetCard', () => {
  test('does not select a widget while creation is pending', async () => {
    const wrapper = mountCreateWidgetCard(true)

    await wrapper.trigger('click')

    expect(wrapper.emitted('widget-variation-selected')).toBeUndefined()
    expect(wrapper.attributes('aria-disabled')).toBe('true')
  })

  test('selects an available widget when creation is not pending', async () => {
    const wrapper = mountCreateWidgetCard(false)

    await wrapper.trigger('click')

    expect(wrapper.emitted('widget-variation-selected')).toEqual([
      [wrapper.props('variation')],
    ])
  })

  test('shows its description when hovered', () => {
    mountCreateWidgetCard(false)
    expect(tooltip.mounted.mock.calls.at(-1)[1].value).toBe('A single number')
  })
})
