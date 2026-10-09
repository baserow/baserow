import { defineComponent } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'

const projectTracker = {
  id: 1,
  slug: 'project-tracker',
  name: 'Project Tracker',
}
const recipeBook = { id: 2, slug: 'recipe-book', name: 'Recipe Book' }

const categories = [
  { id: 1, name: 'Business', templates: [projectTracker] },
  { id: 2, name: 'Personal', templates: [recipeBook] },
]

const ModalStub = defineComponent({
  name: 'Modal',
  props: ['keepContent', 'fullScreen', 'closeButton'],
  methods: {
    show() {},
    hide() {},
  },
  template: '<div><slot /></div>',
})

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
          Modal: ModalStub,
          TemplateList: true,
          TemplateDetails: true,
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

describe('TemplateModal navigation', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.mock.onGet('/templates/').reply(200, categories)
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const stubs = {
    Modal: ModalStub,
    TemplateDetails: defineComponent({
      name: 'TemplateDetails',
      props: ['template', 'categories', 'workspace', 'showBack'],
      emits: ['back', 'installed'],
      template: `<div class="details">
        {{ template.name }}: {{ categories.map((c) => c.name).join(',') }}
        <a class="details__back" @click="$emit('back')" />
      </div>`,
    }),
    TemplateList: defineComponent({
      name: 'TemplateList',
      props: ['categories'],
      emits: ['selected'],
      template: `<div class="list">
        <a class="list__recipe-book" @click="$emit('selected', categories[1].templates[0])" />
      </div>`,
    }),
  }

  const mountAndShow = async (...args) => {
    const wrapper = await testApp.mount(TemplateModal, {
      props: { workspace: { id: 1 } },
      global: { stubs },
    })
    await wrapper.vm.show(...args)
    await flushPromises()
    return wrapper
  }

  it('opens the list, a template from it and goes back', async () => {
    const wrapper = await mountAndShow()

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)

    await wrapper.find('.list__recipe-book').trigger('click')

    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')
    expect(wrapper.find('.list').isVisible()).toBe(false)

    await wrapper.find('.details__back').trigger('click')

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)
  })

  it('opens the template with the given id or slug right away', async () => {
    let wrapper = await mountAndShow(2)
    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')

    wrapper = await mountAndShow('project-tracker')
    expect(wrapper.find('.details').text()).toBe('Project Tracker: Business')
  })

  it('opens the list again when shown after a template was opened', async () => {
    const wrapper = await mountAndShow('project-tracker')

    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)
  })
})
