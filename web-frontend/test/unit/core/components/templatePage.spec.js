import { defineComponent, h, onErrorCaptured } from 'vue'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { clearNuxtData } from '#app'

import { TestApp } from '@baserow/test/helpers/testApp'
import TemplatePage from '@baserow/modules/core/components/template/TemplatePage'

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

describe('TemplatePage', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    clearNuxtData()
    await testApp.afterEach()
  })

  const stubs = {
    TemplateDetails: defineComponent({
      name: 'TemplateDetails',
      props: ['template', 'categories', 'showBack'],
      emits: ['back'],
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

  const mountPage = (slug) => {
    testApp.mock.onGet(`/templates/${slug}/`).reply(200, projectTracker)
    testApp.mock.onGet('/templates/').reply(200, categories)
    return testApp.mount(TemplatePage, {
      route: `/template/${slug}`,
      global: { stubs },
    })
  }

  test('opens the details of the linked template', async () => {
    const wrapper = await mountPage('project-tracker')

    expect(wrapper.find('.details').text()).toBe('Project Tracker: Business')
    expect(wrapper.find('.list').isVisible()).toBe(false)
  })

  test('goes back to the list and opens another template from it', async () => {
    const wrapper = await mountPage('project-tracker')

    await wrapper.find('.details__back').trigger('click')

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)

    await wrapper.find('.list__recipe-book').trigger('click')

    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')
    expect(wrapper.find('.list').isVisible()).toBe(false)
  })

  test('still opens the linked template when the list fails', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/templates/project-tracker/').reply(200, projectTracker)
    testApp.mock.onGet('/templates/').reply(500)

    const wrapper = await testApp.mount(TemplatePage, {
      route: '/template/project-tracker',
      global: { stubs },
    })

    expect(wrapper.find('.details').text()).toBe('Project Tracker:')
  })

  test('fails with a not found error for an unknown template', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/templates/unknown/').reply(404, {
      error: 'ERROR_TEMPLATE_DOES_NOT_EXIST',
    })
    testApp.mock.onGet('/templates/').reply(200, categories)

    // Nuxt shows the error page for an error thrown in the page setup, here it
    // is caught by the parent instead.
    const errors = []
    const Parent = defineComponent({
      setup() {
        onErrorCaptured((error) => {
          errors.push(error)
          return false
        })
        return () => h(TemplatePage)
      },
    })
    await testApp.mount(Parent, {
      route: '/template/unknown',
      global: { stubs },
    })

    expect(errors[0]).toMatchObject({
      statusCode: 404,
      message: 'Template not found.',
      fatal: true,
    })
  })
})
