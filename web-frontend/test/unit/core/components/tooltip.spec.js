import { shallowMount } from '@vue/test-utils'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import tooltip from '@baserow/modules/core/directives/tooltip'

describe('Tooltip directive', () => {
  const Component = {
    template: `
      <ButtonText v-tooltip="tooltipValue">
        test {{ tooltipValue ? 'with tooltip' : 'without tooltip' }}
      </ButtonText>
    `,
    components: { ButtonText },
    directives: { tooltip },
    data() {
      return {
        tooltipValue: 'hello',
      }
    },
  }

  it('shows tooltip when value is provided', async () => {
    const wrapper = shallowMount(Component)
    const buttonText = wrapper.findComponent(ButtonText)

    await buttonText.trigger('mouseenter')

    expect(document.querySelector('.tooltip')).toBeTruthy()
  })

  it('hides tooltip when value is null', async () => {
    const wrapper = shallowMount(Component)
    const buttonText = wrapper.findComponent(ButtonText)

    await wrapper.setData({ tooltipValue: null })

    await buttonText.trigger('mouseenter')

    expect(document.querySelector('.tooltip')).toBeFalsy()
  })

  it('dynamically shows/hides tooltip when value changes', async () => {
    const wrapper = shallowMount(Component)
    const buttonText = wrapper.findComponent(ButtonText)

    await buttonText.trigger('mouseenter')
    expect(document.querySelector('.tooltip')).toBeTruthy()

    await wrapper.setData({ tooltipValue: null })
    expect(document.querySelector('.tooltip')).toBeFalsy()

    await wrapper.setData({ tooltipValue: 'new tooltip' })
    await buttonText.trigger('mouseenter')
    expect(document.querySelector('.tooltip')).toBeTruthy()
  })

  afterEach(() => {
    const tooltips = document.querySelectorAll('.tooltip')
    tooltips.forEach((tooltip) => tooltip.remove())
  })
})
