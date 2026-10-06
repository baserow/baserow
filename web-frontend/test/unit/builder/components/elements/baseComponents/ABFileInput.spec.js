import { mountSuspended } from '@nuxt/test-utils/runtime'
import ABFileInput from '@baserow/modules/builder/components/elements/baseComponents/ABFileInput.vue'

describe('ABFileInput', () => {
  let openFilePicker = null

  beforeEach(() => {
    // The component opens the native file picker by clicking its hidden input.
    openFilePicker = vi
      .spyOn(HTMLInputElement.prototype, 'click')
      .mockImplementation(() => {})
  })

  afterEach(() => {
    openFilePicker.mockRestore()
  })

  const mountComponent = (props = {}) => {
    return mountSuspended(ABFileInput, {
      props: { modelValue: null, multiple: false, ...props },
    })
  }

  test('renders a plain help text as paragraphs without interpreting markdown', async () => {
    const wrapper = await mountComponent({
      helpText: 'Drop **files** here\nor click to select',
    })

    const helpText = wrapper.find('.ab-file-input__help-text')
    expect(helpText.element.tagName).toBe('DIV')
    expect(helpText.findAll('p.ab-text').map((p) => p.text())).toEqual([
      'Drop **files** here',
      'or click to select',
    ])
    expect(helpText.find('strong').exists()).toBe(false)
  })

  test('renders a markdown help text', async () => {
    const wrapper = await mountComponent({
      helpText: 'Drop **files** here\n\nor click to select',
      helpTextFormat: 'markdown',
    })

    const helpText = wrapper.find('.ab-file-input__help-text')
    expect(helpText.find('p.ab-text strong').text()).toBe('files')
    expect(helpText.findAll('p.ab-text')).toHaveLength(2)
  })

  test.each([
    ['Enter', 'Enter'],
    ['Space', ' '],
  ])('opens the file picker on %s on the drop zone', async (_, key) => {
    const wrapper = await mountComponent()

    await wrapper.find('.ab-file-input').trigger('keydown', { key })

    expect(openFilePicker).toHaveBeenCalledTimes(1)
  })

  test('leaves Enter on a link inside the help text to the link', async () => {
    const wrapper = await mountComponent({
      helpText: 'Read the [docs](https://baserow.io) first',
      helpTextFormat: 'markdown',
    })

    await wrapper
      .find('.ab-file-input__help-text a')
      .trigger('keydown', { key: 'Enter' })

    expect(openFilePicker).not.toHaveBeenCalled()
  })

  test('does not open the file picker when a link in the help text is clicked', async () => {
    const wrapper = await mountComponent({
      helpText: 'Read the [docs](https://baserow.io) first',
      helpTextFormat: 'markdown',
    })
    // Keep jsdom from trying to navigate to the external page.
    wrapper.element.addEventListener(
      'click',
      (event) => event.preventDefault(),
      true
    )

    await wrapper.find('.ab-file-input__help-text a').trigger('click')
    expect(openFilePicker).not.toHaveBeenCalled()

    await wrapper.find('.ab-file-input').trigger('click')
    expect(openFilePicker).toHaveBeenCalledTimes(1)
  })
})
