import { defineComponent } from 'vue'
import { clearNuxtData } from '#imports'
import flushPromises from 'flush-promises'

import TemplatePage from '@baserow/modules/core/pages/template'
import { TestApp } from '@baserow/test/helpers/testApp'

const TemplatePreviewStub = defineComponent({
  props: ['template'],
  template: '<p>Preview {{ template.name }}</p>',
})

describe('Standalone template page', () => {
  let testApp

  beforeEach(() => {
    clearNuxtData()
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    clearNuxtData()
  })

  const mountPage = (slug) =>
    testApp.mount(TemplatePage, {
      route: `/template/${slug}`,
      global: { stubs: { TemplatePreview: TemplatePreviewStub } },
    })

  test('fetches and renders the requested template on cold entry', async () => {
    testApp.mock
      .onGet('/templates/cold-entry/')
      .reply(200, { id: 1, name: 'Cold template', workspace_id: 1 })

    const wrapper = await mountPage('cold-entry')

    expect(wrapper.text()).toBe('Preview Cold template')
  })

  test('fetches the new template when the route slug changes', async () => {
    testApp.mock
      .onGet('/templates/first-entry/')
      .reply(200, { id: 1, name: 'First template', workspace_id: 1 })
    testApp.mock
      .onGet('/templates/second-entry/')
      .reply(200, { id: 2, name: 'Second template', workspace_id: 2 })
    const wrapper = await mountPage('first-entry')
    expect(wrapper.text()).toBe('Preview First template')

    await testApp.getApp().$router.push('/template/second-entry')
    await flushPromises()

    expect(wrapper.text()).toBe('Preview Second template')
  })

  test('keeps the error fallback for an unavailable template', async () => {
    testApp.mock.onGet('/templates/unavailable/').reply(404)

    const wrapper = await mountPage('unavailable')

    expect(wrapper.text()).toBe('error')
  })
})
