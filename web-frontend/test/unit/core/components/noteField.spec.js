import { mountSuspended } from '@nuxt/test-utils/runtime'
import NoteField from '@baserow/modules/core/components/NoteField'

describe('NoteField', () => {
  test('shows the current note and follows the prop', async () => {
    const wrapper = await mountSuspended(NoteField, {
      props: { value: 'Before' },
    })

    expect(wrapper.find('textarea').element.value).toBe('Before')

    await wrapper.setProps({ value: 'After' })

    expect(wrapper.find('textarea').element.value).toBe('After')
  })

  test('emits a valid note', async () => {
    const wrapper = await mountSuspended(NoteField, { props: { value: '' } })

    await wrapper.find('textarea').setValue('Why **this** step')

    expect(wrapper.emitted('input')).toEqual([['Why **this** step']])
  })

  test('does not emit a note that is too long', async () => {
    const wrapper = await mountSuspended(NoteField, {
      props: { value: '', maxLength: 10 },
    })

    await wrapper.find('textarea').setValue('a'.repeat(11))

    expect(wrapper.emitted('input')).toBeUndefined()
    expect(wrapper.find('.control__messages--error').exists()).toBe(true)
  })

  test('keeps the typed text when the value changes while focused', async () => {
    const wrapper = await mountSuspended(NoteField, {
      props: { value: 'abc' },
    })
    const textarea = wrapper.find('textarea')

    await textarea.trigger('focus')
    await textarea.setValue('abcd')
    // The response of an earlier save brings the older text back.
    await wrapper.setProps({ value: 'abc' })

    expect(textarea.element.value).toBe('abcd')

    // Once the latest save is confirmed and the field is left, it follows the
    // value again.
    await wrapper.setProps({ value: 'abcd' })
    await textarea.trigger('blur')
    await wrapper.setProps({ value: 'from undo' })

    expect(textarea.element.value).toBe('from undo')
  })

  test('shows the saved note again when a valid field loses focus', async () => {
    const wrapper = await mountSuspended(NoteField, {
      props: { value: 'abc' },
    })
    const textarea = wrapper.find('textarea')

    await textarea.trigger('focus')
    await wrapper.setProps({ value: 'changed by someone else' })
    expect(textarea.element.value).toBe('abc')

    await textarea.trigger('blur')

    expect(textarea.element.value).toBe('changed by someone else')
  })

  test('keeps a rejected note visible when the field loses focus', async () => {
    const wrapper = await mountSuspended(NoteField, {
      props: { value: 'abc', maxLength: 10 },
    })
    const textarea = wrapper.find('textarea')

    await textarea.trigger('focus')
    await textarea.setValue('a'.repeat(11))
    await textarea.trigger('blur')

    expect(textarea.element.value).toBe('a'.repeat(11))
  })
})
