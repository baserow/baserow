import { mountSuspended } from '@nuxt/test-utils/runtime'
import { reactive } from 'vue'
import FileInputElement from '@baserow_enterprise/builder/components/elements/FileInputElement.vue'

describe('FileInputElement', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
  })

  const mountFileInput = async (allowedFiletypes) => {
    const page = reactive({ id: 1, elements: [] })
    const builder = { id: 1, theme: {}, pages: [page] }
    const mode = 'public'
    const element = {
      id: 42,
      type: 'input_file',
      page_id: page.id,
      label: { formula: '' },
      help_text: { formula: '' },
      default_url: { formula: '' },
      default_name: { formula: '' },
      required: false,
      multiple: false,
      preview: false,
      max_filesize: 5,
      allowed_filetypes: allowedFiletypes,
      styles: {},
    }
    await useNuxtApp().$store.dispatch('element/forceCreate', { page, element })

    wrapper = await mountSuspended(FileInputElement, {
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
    return wrapper
  }

  test.each([
    [['image/jpg'], 'image/jpeg'],
    [['image/jpeg'], 'image/jpeg'],
    [['IMAGE/JPG'], 'image/jpeg'],
    [['application/pdf'], 'application/pdf'],
    [['text/csv'], 'text/csv'],
    [['image/svg+xml'], 'image/svg+xml'],
    [
      [
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ],
    [['jpg'], '.jpg'],
    [['.jpg'], '.jpg'],
    [['image/*', 'audio/*', 'video/*'], 'image/*,audio/*,video/*'],
    [['text/*', 'application/*'], 'text/*,application/*'],
    [['', 'jpg', 'application/pdf', '.png'], '.jpg,application/pdf,.png'],
    [[], undefined],
    [[''], undefined],
  ])(
    'uses %j as the file picker filter %s',
    async (allowedFiletypes, expectedAccept) => {
      const wrapper = await mountFileInput(allowedFiletypes)

      expect(wrapper.get('input[type="file"]').attributes('accept')).toBe(
        expectedAccept
      )
    }
  )
})
