import { shallowMount } from '@vue/test-utils'
import Alert from '@baserow/modules/core/components/Alert'

describe('Alert.vue', () => {
  it('renders the alert title and message', () => {
    const title = 'This is an alert title.'
    const message = 'This is an alert message.'
    const wrapper = shallowMount(Alert, {
      slots: {
        title,
        default: message,
      },
    })
    expect(wrapper.find('.alert__title').text()).toMatch('title')
    expect(wrapper.find('.alert__message').text()).toMatch(message)
  })

  it('emits the close event when the close button is clicked', () => {
    const closeButton = true
    const wrapper = shallowMount(Alert, {
      propsData: { closeButton },
    })
    wrapper.find('.alert__close').trigger('click')
    expect(wrapper.emitted().close).toBeTruthy()
  })

  it('sets the alert type based on the type prop', () => {
    const type = 'success'
    const wrapper = shallowMount(Alert, {
      propsData: { type },
    })
    expect(wrapper.classes()).toContain(`alert--${type}`)
  })
  it.each(['default', 'compact'])(
    'renders an error using the %s appearance',
    (appearance) => {
      const wrapper = shallowMount(Alert, {
        props: { type: 'error', appearance },
        slots: { default: 'There is not enough room for a new snapshot.' },
      })

      expect(wrapper.html()).toMatchSnapshot()
    }
  )
})
