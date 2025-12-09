import { shallowMount } from '@vue/test-utils'
import FormTextarea from '@baserow/modules/core/components/FormTextarea.vue'

describe('FormTextarea.vue', () => {
  it('calls resizeTextArea when value changes if autoExpandable is true', async () => {
    const wrapper = shallowMount(FormTextarea, {
      propsData: {
        autoExpandable: true,
        value: 'initial value',
      },
    })

    const spy = vi.spyOn(wrapper.vm, 'resizeTextArea')

    await wrapper.setProps({ value: 'new value' })

    expect(spy).toHaveBeenCalled()
  })

  it('does not call resizeTextArea when value changes if autoExpandable is false', async () => {
    const wrapper = shallowMount(FormTextarea, {
      propsData: {
        autoExpandable: false,
        value: 'initial value',
      },
    })

    const spy = vi.spyOn(wrapper.vm, 'resizeTextArea')

    await wrapper.setProps({ value: 'new value' })

    expect(spy).not.toHaveBeenCalled()
  })

  it('calls resizeTextArea on mount if autoExpandable is true', async () => {
    const wrapper = shallowMount(FormTextarea, {
      propsData: {
        autoExpandable: true,
      },
    })

    const spy = vi.spyOn(wrapper.vm, 'resizeTextArea')

    await wrapper.setProps({ value: 'new value' })

    expect(spy).toHaveBeenCalled()
  })

  it('does not call resizeTextArea on mount if autoExpandable is false', () => {
    const wrapper = shallowMount(FormTextarea, {
      propsData: {
        autoExpandable: false,
      },
    })

    const spy = vi.spyOn(wrapper.vm, 'resizeTextArea')

    expect(spy).not.toHaveBeenCalled()
  })

  it('emits input event when textarea value changes', async () => {
    const wrapper = shallowMount(FormTextarea)
    const textarea = wrapper.find('textarea')

    await textarea.setValue('new value')

    expect(wrapper.emitted('input')[0]).toEqual(['new value'])
  })

  it('sets textarea value when value prop changes', async () => {
    const wrapper = shallowMount(FormTextarea, {
      propsData: {
        value: 'initial value',
      },
    })

    await wrapper.setProps({ value: 'new value' })

    const textarea = wrapper.find('textarea')
    expect(textarea.element.value).toBe('new value')
  })

  it('sets textarea placeholder when placeholder prop is provided', () => {
    const wrapper = shallowMount(FormTextarea, {
      propsData: {
        placeholder: 'Enter text here',
      },
    })

    const textarea = wrapper.find('textarea')
    expect(textarea.element.placeholder).toBe('Enter text here')
  })
})
