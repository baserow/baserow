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

  it('applies the right position and no arrow classes', async () => {
    const PositionedComponent = {
      template: `
        <ButtonText
          v-tooltip="'hello'"
          tooltip-position="right"
          tooltip-no-arrow
        >test</ButtonText>
      `,
      components: { ButtonText },
      directives: { tooltip },
    }
    const wrapper = shallowMount(PositionedComponent)

    await wrapper.findComponent(ButtonText).trigger('mouseenter')

    const element = document.querySelector('.tooltip')
    expect(element.classList.contains('tooltip--right')).toBe(true)
    expect(element.classList.contains('tooltip--no-arrow')).toBe(true)
  })

  it.each(['top', 'bottom'])(
    'keeps a %s tooltip inside either viewport edge with its arrow on the target',
    async (position) => {
      const wrapper = shallowMount(Component, {
        attrs: { 'tooltip-position': position },
      })
      const button = wrapper.findComponent(ButtonText)
      const viewport = vi
        .spyOn(document.documentElement, 'clientWidth', 'get')
        .mockReturnValue(1000)
      let targetLeft = 960
      const rectangles = vi
        .spyOn(Element.prototype, 'getBoundingClientRect')
        .mockImplementation(function () {
          return this.classList.contains('tooltip')
            ? { width: 280, height: 80 }
            : {
                left: targetLeft,
                right: targetLeft + 16,
                width: 16,
                top: 100,
                bottom: 116,
              }
        })

      try {
        await button.trigger('mouseenter')
        const element = document.querySelector('.tooltip')
        // The centered tooltip is shifted left, while its arrow stays on the icon.
        expect(element.style.left).toBe('852px')
        expect(
          element.style.getPropertyValue('--tooltip-cursor-position-left')
        ).toBe('256px')

        targetLeft = 12
        window.dispatchEvent(new Event('resize'))
        expect(element.style.left).toBe('148px')
        expect(
          element.style.getPropertyValue('--tooltip-cursor-position-left')
        ).toBe('12px')

        targetLeft = 492
        window.dispatchEvent(new Event('resize'))
        expect(element.style.left).toBe('500px')
        expect(
          element.style.getPropertyValue('--tooltip-cursor-position-left')
        ).toBe('140px')
      } finally {
        wrapper.unmount()
        rectangles.mockRestore()
        viewport.mockRestore()
      }
    }
  )

  describe('with a show delay', () => {
    const DelayedComponent = {
      template: `
        <ButtonText v-tooltip="'hello'" tooltip-show-delay="500">
          test
        </ButtonText>
      `,
      components: { ButtonText },
      directives: { tooltip },
    }

    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('only shows the tooltip after the delay', async () => {
      const wrapper = shallowMount(DelayedComponent)
      const buttonText = wrapper.findComponent(ButtonText)

      await buttonText.trigger('mouseenter')
      expect(document.querySelector('.tooltip')).toBeFalsy()

      vi.advanceTimersByTime(499)
      expect(document.querySelector('.tooltip')).toBeFalsy()

      vi.advanceTimersByTime(1)
      expect(document.querySelector('.tooltip')).toBeTruthy()
    })

    it('never shows the tooltip when leaving before the delay', async () => {
      const wrapper = shallowMount(DelayedComponent)
      const buttonText = wrapper.findComponent(ButtonText)

      await buttonText.trigger('mouseenter')
      await buttonText.trigger('mouseleave')

      vi.runAllTimers()
      expect(document.querySelector('.tooltip')).toBeFalsy()
    })

    it('never shows the tooltip when unmounted before the delay', async () => {
      const wrapper = shallowMount(DelayedComponent)
      const buttonText = wrapper.findComponent(ButtonText)

      await buttonText.trigger('mouseenter')
      wrapper.unmount()

      vi.runAllTimers()
      expect(document.querySelector('.tooltip')).toBeFalsy()
    })
  })

  afterEach(() => {
    const tooltips = document.querySelectorAll('.tooltip')
    tooltips.forEach((tooltip) => tooltip.remove())
  })
})
