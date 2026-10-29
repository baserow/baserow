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
// A shared template, which lists its own categories.
const crm = {
  id: 5,
  type: 'user',
  slug: 'crm-a1b2c3',
  name: 'CRM',
  categories: [{ id: 3, name: 'Sales' }],
}

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
      emits: ['back', 'outdated'],
      template: `<div class="details">
        {{ template.name }}: {{ categories.map((c) => c.name).join(',') }}
        <a class="details__back" @click="$emit('back')" />
        <a class="details__outdated" @click="$emit('outdated')" />
      </div>`,
    }),
    TemplateList: defineComponent({
      name: 'TemplateList',
      props: ['categories', 'active'],
      emits: ['selected'],
      template: `<div class="list">
        <slot name="head" />
        <a class="list__recipe-book" @click="$emit('selected', categories[1].templates[0])" />
      </div>`,
    }),
    SharedTemplateList: defineComponent({
      name: 'SharedTemplateList',
      emits: ['selected'],
      template: `<div class="shared-list">
        <slot name="head" />
        <a class="shared-list__crm" @click="$emit('selected', crm)" />
      </div>`,
      setup: () => ({ crm }),
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

  test('opens a shared template from the shared tab', async () => {
    const wrapper = await mountPage('project-tracker')

    await wrapper.find('.details__back').trigger('click')
    expect(wrapper.find('.shared-list').exists()).toBe(false)

    await wrapper.findAll('.segment-control__button')[1].trigger('click')
    expect(wrapper.find('.list').isVisible()).toBe(false)

    await wrapper.find('.shared-list__crm').trigger('click')
    const router = useRouter()
    await vi.waitFor(() =>
      expect(router.currentRoute.value.params.slug).toBe('crm-a1b2c3')
    )
    await flushPromises()

    expect(wrapper.find('.details').text()).toBe('CRM: Sales')
    expect(wrapper.find('.shared-list').isVisible()).toBe(false)

    // Reloaded when its install is outdated, keeping its own categories.
    testApp.mock
      .onGet('/templates/crm-a1b2c3/')
      .reply(200, { id: 5, type: 'user', slug: 'crm-a1b2c3', name: 'CRM 2' })
    await wrapper.find('.details__outdated').trigger('click')
    await flushPromises()
    expect(wrapper.find('.details').text()).toBe('CRM 2: Sales')

    await wrapper.find('.details__back').trigger('click')

    expect(wrapper.find('.shared-list').isVisible()).toBe(true)
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

  test('reloads the preview when the install of the shown revision is refused', async () => {
    // The user opened revision 8, then the owner made revision 9 public.
    const crm = {
      id: 5,
      revision_id: 8,
      type: 'user',
      slug: 'crm-a1b2c3',
      name: 'CRM',
      workspace_id: 108,
    }
    const newRevision = {
      ...crm,
      revision_id: 9,
      name: 'CRM 2',
      workspace_id: 109,
    }
    const database = (workspaceId, name) => ({
      id: workspaceId,
      name,
      order: 1,
      type: 'database',
      workspace: { id: workspaceId },
      tables: [],
    })
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/workspaces/').reply(200, [{ id: 1, name: 'First' }])
    testApp.mock.onGet('/applications/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock
      .onGet('/templates/crm-a1b2c3/')
      .replyOnce(200, crm)
      .onGet('/templates/crm-a1b2c3/')
      .replyOnce(200, newRevision)
    testApp.mock.onGet('/templates/').reply(200, categories)
    testApp.mock
      .onGet('/applications/workspace/108/')
      .reply(200, [database(108, 'Leads')])
      .onGet('/applications/workspace/109/')
      .reply(200, [database(109, 'Leads and deals')])
    testApp.mock.onPost('/templates/install/1/5/async/').reply(400, {
      error: 'ERROR_TEMPLATE_UPDATED',
      detail: 'The template was updated after it was opened.',
    })
    // The real details and install button, so that the refusal reaches the page.
    const wrapper = await testApp.mount(TemplatePage, {
      route: '/template/crm-a1b2c3',
      global: {
        stubs: { TemplateList: stubs.TemplateList, TableTemplate: true },
      },
    })
    await flushPromises()
    const applicationNames = () =>
      wrapper.findAll('.tree__link-text').map((link) => link.text())

    expect(wrapper.find('.template-details__name').text()).toBe('CRM')
    expect(applicationNames()).toStrictEqual(['Leads'])

    await wrapper.find('.template-install__use').trigger('click')
    await flushPromises()

    expect(testApp.mock.history.post.map((r) => r.params)).toStrictEqual([
      { revision_id: 8 },
    ])
    expect(
      testApp.mock.history.get.filter((r) => r.url === '/templates/crm-a1b2c3/')
    ).toHaveLength(2)
    expect(wrapper.find('.template-details__name').text()).toBe('CRM 2')
    expect(applicationNames()).toStrictEqual(['Leads and deals'])
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
