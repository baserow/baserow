import { mountSuspended } from '@nuxt/test-utils/runtime'
import TextFormatSelector from '@baserow/modules/builder/components/elements/components/forms/TextFormatSelector.vue'

describe('TextFormatSelector', () => {
  test('offers the plain and markdown formats and emits the selection', async () => {
    const wrapper = await mountSuspended(TextFormatSelector, {
      props: { modelValue: 'plain' },
      mocks: { $t: (key) => key },
    })

    const radioGroup = wrapper.findComponent({ name: 'RadioGroup' })
    expect(radioGroup.props('modelValue')).toBe('plain')
    expect(radioGroup.props('options').map(({ value }) => value)).toEqual([
      'plain',
      'markdown',
    ])

    await radioGroup.vm.$emit('update:modelValue', 'markdown')

    expect(wrapper.emitted('update:modelValue')).toEqual([['markdown']])
  })
})
