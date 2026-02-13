import { mountSuspended } from '@nuxt/test-utils/runtime'
import ButtonText from '@baserow/modules/core/components/ButtonText'

describe('ButtonText.vue', () => {
  it('renders the button text', async () => {
    const text = 'Click me'
    const wrapper = await mountSuspended(ButtonText, {
      slots: {
        default: text,
      },
    })
    expect(wrapper.text()).toMatch(text)
  })

  it('renders an anchor tag when href prop is provided', async () => {
    const href = 'https://example.com'
    const wrapper = await mountSuspended(ButtonText, {
      props: { href },
    })
    expect(wrapper.element.tagName).toBe('A')
  })

  it('emits the click event when clicked', async () => {
    const wrapper = await mountSuspended(ButtonText)
    wrapper.vm.$emit('click')
    expect(wrapper.emitted().click).toBeTruthy()
  })

  it('disables the button when disabled prop is true', async () => {
    const wrapper = await mountSuspended(ButtonText, {
      props: { disabled: true },
    })
    expect(wrapper.attributes('disabled')).toBeDefined()
  })

  it('renders the button with the correct class when type prop is provided', async () => {
    const type = 'secondary'
    const wrapper = await mountSuspended(ButtonText, {
      props: { type },
    })
    expect(wrapper.classes()).toContain(`button-text--${type}`)
  })

  it('renders the button with the correct size when size prop is provided', async () => {
    const size = 'large'
    const wrapper = await mountSuspended(ButtonText, {
      props: { size },
    })
    expect(wrapper.classes()).toContain(`button-text--${size}`)
  })

  it('renders the button with the correct icon when icon prop is provided', async () => {
    const icon = 'iconoir-plus'
    const wrapper = await mountSuspended(ButtonText, {
      props: { icon },
    })
    expect(wrapper.find('.button-text__icon').classes()).toContain(`${icon}`)
  })
})
