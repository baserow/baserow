import { TestApp } from '@baserow/test/helpers/testApp'
import FormulaInputExplorerContext from '@baserow/modules/core/components/formula/FormulaInputExplorerContext.vue'

describe('FormulaInputExplorerContext format picker', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const formatOptions = [
    { value: 'plain', name: 'Plain text' },
    { value: 'markdown', name: 'Markdown' },
  ]

  async function mountContext(props = {}) {
    const wrapper = await testApp.mount(FormulaInputExplorerContext, {
      props: { enabledModes: ['simple'], mode: 'simple', ...props },
    })
    // The context only renders its content once it has been opened.
    wrapper.vm.getRootContext().forceRender()
    await wrapper.vm.$nextTick()
    return wrapper
  }

  const segments = (wrapper) =>
    wrapper.findAll(
      '.formula-input-explorer-context__format .segment-control__button'
    )

  it('renders no footer without the advanced mode nor a format to pick', async () => {
    const wrapper = await mountContext()

    expect(
      wrapper.find('.formula-input-explorer-context__footer').exists()
    ).toBe(false)
  })

  it('renders the format picker on its own', async () => {
    const wrapper = await mountContext({ formatOptions })

    const picker = wrapper.find('.formula-input-explorer-context__format')
    expect(picker.attributes('aria-label')).toBe(
      'formulaInputExplorerContext.formatLabel'
    )
    expect(segments(wrapper).map((segment) => segment.text())).toEqual([
      'Plain text',
      'Markdown',
    ])
    expect(wrapper.text()).not.toContain(
      'formulaInputExplorerContext.useAdvancedInput'
    )
  })

  it('renders no format picker with a single format', async () => {
    const wrapper = await mountContext({
      enabledModes: ['simple', 'advanced'],
      formatOptions: [formatOptions[0]],
    })

    expect(
      wrapper.find('.formula-input-explorer-context__footer').exists()
    ).toBe(true)
    expect(
      wrapper.find('.formula-input-explorer-context__format').exists()
    ).toBe(false)
  })

  it('marks the current format as active', async () => {
    const wrapper = await mountContext({ formatOptions, format: 'markdown' })

    expect(
      wrapper
        .find(
          '.formula-input-explorer-context__format .segment-control__button--active'
        )
        .text()
    ).toBe('Markdown')
  })

  it('falls back to the first format when the current one is unknown', async () => {
    const wrapper = await mountContext({ formatOptions, format: 'html' })

    expect(
      wrapper
        .find(
          '.formula-input-explorer-context__format .segment-control__button--active'
        )
        .text()
    ).toBe('Plain text')
  })

  it('emits the picked format', async () => {
    const wrapper = await mountContext({ formatOptions })

    await segments(wrapper).at(1).trigger('click')

    expect(wrapper.emitted('format-changed')).toEqual([['markdown']])
  })

  it('emits nothing when the active format is picked again', async () => {
    const wrapper = await mountContext({ formatOptions, format: 'markdown' })

    await segments(wrapper).at(1).trigger('click')

    expect(wrapper.emitted('format-changed')).toBeUndefined()
  })
})
