import { defineComponent } from 'vue'
import { shallowMount } from '@vue/test-utils'

import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'

describe('TemplateModal', () => {
  const mountComponent = () => {
    return shallowMount(TemplateModal, {
      propsData: {
        workspace: {
          id: 1,
        },
      },
      global: {
        stubs: {
          Modal: defineComponent({
            name: 'Modal',
            props: ['keepContent', 'fullScreen', 'closeButton'],
            template: '<div><slot /></div>',
          }),
          TemplateHeader: true,
          TemplateCategories: true,
          TemplatePreview: true,
        },
      },
    })
  }

  it('keeps the root modal content mounted while closed', () => {
    const wrapper = mountComponent()

    expect(wrapper.findComponent({ name: 'Modal' }).props('keepContent')).toBe(
      ''
    )
  })
})
