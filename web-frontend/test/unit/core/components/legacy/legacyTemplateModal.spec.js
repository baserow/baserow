import { defineComponent } from 'vue'
import { shallowMount } from '@vue/test-utils'

import LegacyTemplateModal from '@baserow/modules/core/components/template/legacy/LegacyTemplateModal'

describe('LegacyTemplateModal', () => {
  const mountComponent = () => {
    return shallowMount(LegacyTemplateModal, {
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
          LegacyTemplateHeader: true,
          LegacyTemplateCategories: true,
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
