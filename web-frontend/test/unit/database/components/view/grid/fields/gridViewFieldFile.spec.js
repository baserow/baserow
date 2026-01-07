import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldFile from '@baserow/modules/database/components/view/grid/fields/GridViewFieldFile'
import UploadFileUserFileUpload from '@baserow/modules/core/components/files/UploadFileUserFileUpload'

describe('GridViewFieldFile component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (props, slots = {}) => {
    return testApp.mount(GridViewFieldFile, { props, slots })
  }

  const field = {
    id: 1,
    name: 'File',
    order: 0,
    type: 'file',
    primary: false,
    text_default: '',
    _: {
      loading: false,
    },
  }

  const event = {
    target: {
      files: [
        {
          name: 'test.txt',
          size: 500,
          type: 'text/plain',
        },
      ],
    },
  }

  test('File upload modal should stay open when trash button is clicked', async () => {
    const wrapper = await mountComponent({
      field,
      readOnly: false,
      selected: true,
      storePrefix: 'page/',
      value: [],
      workspaceId: 10,
    })

    await wrapper.find('.grid-field-file__item-add').trigger('click')

    const modal = wrapper.findComponent(UploadFileUserFileUpload)

    // Manually call file input change event handler
    modal.vm.addFile(event)
    await wrapper.vm.$nextTick()

    const documentClick = vi.fn()
    document.body.addEventListener('click', documentClick)

    // After clicking remove file, the modal should still be visible
    await modal.find('.upload-files__state-link').trigger('click')
    expect(documentClick).not.toHaveBeenCalled()
  })
})
