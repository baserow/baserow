import { mountSuspended } from '@nuxt/test-utils/runtime'
import ABFormGroup from '@baserow/modules/builder/components/elements/baseComponents/ABFormGroup.vue'

describe('ABFormGroup', () => {
  const mountComponent = (props = {}) => {
    return mountSuspended(ABFormGroup, {
      props,
      slots: { default: '<input />' },
    })
  }

  test('renders a plain label as it is', async () => {
    const wrapper = await mountComponent({ label: '**Name**' })

    const label = wrapper.find('.ab-form-group__label')
    expect(label.text()).toBe('**Name**')
    expect(label.find('strong').exists()).toBe(false)
  })

  test('renders a markdown label inline', async () => {
    const wrapper = await mountComponent({
      label: 'Your **name** ([why?](https://baserow.io))',
      labelFormat: 'markdown',
    })

    const label = wrapper.find('.ab-form-group__label')
    expect(label.find('strong').text()).toBe('name')
    expect(label.find('a.ab-link').attributes('href')).toBe(
      'https://baserow.io'
    )
    expect(label.find('p').exists()).toBe(false)
  })

  test('marks a required field with an asterisk after the label', async () => {
    const wrapper = await mountComponent({
      label: '**Name**',
      labelFormat: 'markdown',
      required: true,
    })

    const label = wrapper.find('.ab-form-group__label')
    expect(label.text()).toBe('Name *')
    expect(label.find('span[title="error.requiredField"]').exists()).toBe(true)
  })

  test('renders no label element without a label', async () => {
    const wrapper = await mountComponent({ required: true })

    expect(wrapper.find('.ab-form-group__label').exists()).toBe(false)
    expect(wrapper.find('input').exists()).toBe(true)
  })
})
