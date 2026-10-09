import { TestApp } from '@baserow/test/helpers/testApp'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput.vue'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField.vue'

describe('ApplicationBuilderFormulaInput formats', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountInput = (value, attrs = {}) => {
    const page = { id: 1, elements: [], dataSources: [], _: {} }
    const builder = { id: 1, pages: [page] }
    return testApp.mount(ApplicationBuilderFormulaInput, {
      props: { value },
      attrs,
      global: {
        provide: {
          applicationContext: { builder, page, mode: 'editing' },
          elementPage: page,
        },
      },
    })
  }

  const formulaInput = (wrapper) => wrapper.findComponent(FormulaInputField)

  test('emits the value with the picked format right away', async () => {
    const wrapper = await mountInput({ formula: "'Name'", mode: 'simple' })

    formulaInput(wrapper).vm.$emit('update:format', 'markdown')

    const value = { formula: "'Name'", mode: 'simple', format: 'markdown' }
    expect(wrapper.emitted('input').at(-1)).toEqual([value])
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([value])
  })

  test('leaves the format key out when plain is picked', async () => {
    const wrapper = await mountInput({
      formula: "'Name'",
      mode: 'simple',
      format: 'markdown',
    })

    formulaInput(wrapper).vm.$emit('update:format', 'plain')

    const [value] = wrapper.emitted('input').at(-1)
    expect(value).toEqual({ formula: "'Name'", mode: 'simple' })
    expect(value).not.toHaveProperty('format')
  })

  test('keeps the format when the formula changes', async () => {
    const wrapper = await mountInput({
      formula: "'Name'",
      mode: 'simple',
      format: 'markdown',
    })

    formulaInput(wrapper).vm.$emit('input', "'**Name**'")

    expect(wrapper.emitted('input').at(-1)).toEqual([
      { formula: "'**Name**'", mode: 'simple', format: 'markdown' },
    ])
  })

  test('follows the format of the value', async () => {
    const wrapper = await mountInput({
      formula: "'Name'",
      mode: 'simple',
      format: 'markdown',
    })
    expect(formulaInput(wrapper).props('format')).toBe('markdown')

    // A value that lost its key went back to plain.
    await wrapper.setProps({ value: { formula: "'Name'", mode: 'simple' } })

    expect(formulaInput(wrapper).props('format')).toBe('plain')
  })

  test('passes the allowed formats on to the formula input', async () => {
    const wrapper = await mountInput(
      { formula: "'Name'", mode: 'simple' },
      { allowedFormats: ['plain', 'markdown'] }
    )

    expect(formulaInput(wrapper).props('allowedFormats')).toEqual([
      'plain',
      'markdown',
    ])
  })
})
