import { mountSuspended } from '@nuxt/test-utils/runtime'
import FormulaFormatSelector from '@baserow/modules/builder/components/elements/components/forms/FormulaFormatSelector.vue'

describe('FormulaFormatSelector', () => {
  const mountComponent = (modelValue) =>
    mountSuspended(FormulaFormatSelector, {
      props: { modelValue },
      mocks: { $t: (key) => key },
    })

  const radioGroup = (wrapper) => wrapper.findComponent({ name: 'RadioGroup' })

  test('reads the format from the formula object and defaults to plain', async () => {
    const plain = await mountComponent({ formula: "'x'", mode: 'simple' })
    expect(radioGroup(plain).props('modelValue')).toBe('plain')

    const markdown = await mountComponent({
      formula: "'x'",
      mode: 'simple',
      format: 'markdown',
    })
    expect(radioGroup(markdown).props('modelValue')).toBe('markdown')

    const empty = await mountComponent(undefined)
    expect(radioGroup(empty).props('modelValue')).toBe('plain')
  })

  test('writes the format onto the formula object, keeping its other keys', async () => {
    const wrapper = await mountComponent({
      formula: "get('page_parameter.id')",
      mode: 'simple',
      version: '0.1',
    })

    await radioGroup(wrapper).vm.$emit('update:modelValue', 'markdown')

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [
        {
          formula: "get('page_parameter.id')",
          mode: 'simple',
          version: '0.1',
          format: 'markdown',
        },
      ],
    ])
  })

  test('drops the key again for the plain default', async () => {
    const wrapper = await mountComponent({
      formula: "'x'",
      mode: 'simple',
      format: 'markdown',
    })

    await radioGroup(wrapper).vm.$emit('update:modelValue', 'plain')

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [{ formula: "'x'", mode: 'simple' }],
    ])
  })

  test('always emits a formula object, even for an untouched formula', async () => {
    const wrapper = await mountComponent({})

    await radioGroup(wrapper).vm.$emit('update:modelValue', 'markdown')

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [{ formula: '', format: 'markdown' }],
    ])
  })
})
