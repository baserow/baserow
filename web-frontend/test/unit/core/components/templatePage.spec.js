import { defineComponent, h, onErrorCaptured } from 'vue'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { clearNuxtData, useNuxtApp, useRouter } from '#app'

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
      props: ['categories', 'active'],
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

  test('shows the toasts, as it has no app layout', async () => {
    const wrapper = await mountPage('project-tracker')

    await testApp.store.dispatch('toast/add', {
      type: 'installTemplate',
      data: { jobId: 10, template_name: 'Project Tracker' },
    })
    await flushPromises()

    expect(wrapper.find('.install-template-toast').exists()).toBe(true)
  })

  test('goes back to the list and opens another template from it', async () => {
    const wrapper = await mountPage('project-tracker')

    await wrapper.find('.details__back').trigger('click')

    expect(wrapper.find('.details').exists()).toBe(false)
    expect(wrapper.find('.list').isVisible()).toBe(true)

    await wrapper.find('.list__recipe-book').trigger('click')

    // The URL follows the opened template.
    const router = useRouter()
    await vi.waitFor(() =>
      expect(router.currentRoute.value.params.slug).toBe('recipe-book')
    )
    await flushPromises()

    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')
    expect(wrapper.find('.list').isVisible()).toBe(false)
  })

  test('shows the template of the URL when it changes', async () => {
    const wrapper = await mountPage('project-tracker')
    const router = useRouter()

    await wrapper.find('.details__back').trigger('click')
    await router.push('/template/recipe-book')
    await flushPromises()

    expect(wrapper.find('.details').text()).toBe('Recipe Book: Personal')
    expect(wrapper.find('.list').isVisible()).toBe(false)

    await router.push('/template/project-tracker')
    await flushPromises()

    expect(wrapper.find('.details').text()).toBe('Project Tracker: Business')
  })

  test('lets the list claim the search shortcut only while it is shown', async () => {
    const wrapper = await mountPage('project-tracker')
    const list = () => wrapper.findComponent({ name: 'TemplateList' })

    expect(list().props('active')).toBe(false)

    await wrapper.find('.details__back').trigger('click')

    expect(list().props('active')).toBe(true)
  })

  test('turns the search shortcut into a priority bus event', async () => {
    await mountPage('project-tracker')
    const { $priorityBus } = useNuxtApp()
    const listener = vi.fn()
    $priorityBus.$on('start-search', $priorityBus.level.HIGHEST, listener)

    document.body.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'S',
        ctrlKey: true,
        metaKey: true,
        shiftKey: true,
      })
    )

    $priorityBus.$off('start-search', listener)
    expect(listener).toHaveBeenCalledTimes(1)
  })

  test('loads the workspaces to install into for a logged in user', async () => {
    // A user without workspaces who hasn't finished the onboarding still sees
    // the template instead of being sent to the onboarding.
    testApp.authenticate({
      id: 1,
      preferences: {},
      completed_onboarding: false,
    })
    testApp.mock.onGet('/workspaces/').reply(200, [])
    testApp.mock.onGet('/applications/').reply(200, [])

    const wrapper = await mountPage('project-tracker')

    expect(testApp.mock.history.get.map((r) => r.url)).toContain('/workspaces/')
    expect(useRouter().currentRoute.value.name).toBe('template')
    expect(wrapper.find('.details').text()).toBe('Project Tracker: Business')
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
