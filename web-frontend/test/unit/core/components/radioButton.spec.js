import { mountSuspended } from '@nuxt/test-utils/runtime'

import RadioButton from '@baserow/modules/core/components/RadioButton'

describe('RadioButton.vue', () => {
  it('renders the button', async () => {
    const wrapper = await mountSuspended(RadioButton)

    expect(wrapper.html()).toMatchSnapshot()
  })

  it('passes the correct props to the button', async () => {
    const propsData = {
      loading: true,
      disabled: true,
      icon: 'test-icon',
      title: 'test-title',
    }
    const wrapper = await mountSuspended(RadioButton, { props: propsData })

    expect(wrapper.html()).toMatchSnapshot()
  })

  it('emits input event with the correct value when the button is clicked', async () => {
    const value = 'test'
    const onClick = vi.fn()
    const wrapper = await mountSuspended(RadioButton, {
      props: {
        value,
        onClick,
      },
    })

    await wrapper.findComponent({ name: 'Button' }).trigger('click')

    expect(onClick).toHaveBeenCalled()
  })
})
