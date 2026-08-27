import { mountSuspended } from '@nuxt/test-utils/runtime'
import FileInputElement from '@baserow_enterprise/builder/components/elements/FileInputElement.vue'

describe('FileInputElement', () => {
  let store = null

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  const mountFileInput = async (elementOverrides = {}) => {
    const page = { id: 1, elements: [] }
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const mode = 'public'
    const element = {
      id: 44,
      type: 'input_file',
      label: { mode: 'raw', formula: 'Your **CV** ([tips](/tips))' },
      label_format: 'plain',
      help_text: { mode: 'raw', formula: '# Drop it\n\nPDF **only**' },
      help_text_format: 'plain',
      default_url: { formula: '' },
      default_name: { formula: '' },
      required: false,
      multiple: false,
      preview: false,
      allowed_filetypes: [],
      max_filesize: 5,
      page_id: page.id,
      styles: {},
      ...elementOverrides,
    }

    store.dispatch('element/forceCreate', { page, element })

    return mountSuspended(FileInputElement, {
      props: { element },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: { builder, page, mode },
          element,
          workspace: {},
        },
      },
    })
  }

  test('renders the label and help text as-is by default', async () => {
    const wrapper = await mountFileInput()

    expect(wrapper.find('.ab-form-group__label').text()).toBe(
      'Your **CV** ([tips](/tips))'
    )
    expect(wrapper.find('.ab-file-input .ab-heading').exists()).toBe(false)
    expect(wrapper.find('.ab-file-input').text()).toContain('# Drop it')
  })

  test('renders a Markdown label with links and block Markdown help text', async () => {
    const wrapper = await mountFileInput({
      label_format: 'markdown',
      help_text_format: 'markdown',
    })

    const label = wrapper.find('.ab-form-group__label')
    expect(label.find('strong').text()).toBe('CV')
    expect(label.find('a.ab-link').attributes('href')).toBe('/tips')

    const helpText = wrapper.find('.ab-file-input')
    expect(helpText.find('.ab-heading').text()).toBe('Drop it')
    expect(helpText.find('strong').text()).toBe('only')
  })
})
