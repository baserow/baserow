import { defineComponent } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
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

  it('shows the categories and the default template category by their shown name', async () => {
    const testApp = new TestApp()
    const template = (id, isDefault) => ({
      id,
      name: `Template ${id}`,
      slug: `template-${id}`,
      keywords: '',
      icon: 'iconoir-table',
      is_default: isDefault,
    })
    testApp.mock.onGet('/templates/').reply(200, [
      { id: 1, name: 'Unknown Category', templates: [template(1, false)] },
      { id: 2, name: '🔥 Most Popular', templates: [template(2, true)] },
    ])
    const wrapper = await testApp.mount(LegacyTemplateModal, {
      props: { workspace: { id: 1 } },
      global: { stubs: { Modal: ModalStub, TemplatePreview: true } },
    })

    await wrapper.vm.show()
    await flushPromises()

    expect(
      wrapper.findAll('.templates__category-link').map((a) => a.text())
    ).toEqual(['templateCategoryNames.🔥 Most Popular', 'Unknown Category'])
    expect(wrapper.find('.templates__header-title small').text()).toBe(
      'templateCategoryNames.🔥 Most Popular'
    )
    await testApp.afterEach()
  })
})
