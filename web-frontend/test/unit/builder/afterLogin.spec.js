import { createRouter, createMemoryHistory } from 'vue-router'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { AfterLoginEvent } from '@baserow/modules/builder/eventTypes'
import { OpenPageWorkflowActionType } from '@baserow/modules/builder/workflowActionTypes'
import { populateWorkflowAction } from '@baserow/modules/builder/store/builderWorkflowAction'

describe('After login navigation', () => {
  let testApp
  let app
  let router
  let context

  beforeEach(async () => {
    testApp = new TestApp()
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
      ],
    })
    await router.push('/login?next=%252Foriginal')
    const { $i18n, $store, $registry } = testApp.getApp()
    app = { $i18n, $store, $registry, $router: router }
    const registry = app.$registry
    const openPage = new OpenPageWorkflowActionType({ app })
    app.$registry = {
      get: (kind, type) =>
        kind === 'workflowAction' && type === 'open_page'
          ? openPage
          : registry.get(kind, type),
      getAll: (...args) => registry.getAll(...args),
    }
    const page = { id: 1, graph: {}, shared: false }
    const builder = { id: 1, pages: [page, { id: 2, shared: true }] }
    context = {
      builder,
      page,
      mode: 'public',
      element: { id: 10, page_id: 1, type: 'button', parent_element_id: null },
    }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('waits for configured navigation and does not override it with next', async () => {
    let release
    const blocked = new Promise((resolve) => {
      release = resolve
    })
    router.beforeEach(async (to) => {
      if (to.path === '/page-sso') await blocked
    })
    const action = populateWorkflowAction({
      id: 1,
      type: 'open_page',
      navigation_type: 'custom',
      navigate_to_url: { formula: "'/page-sso'" },
      target: 'self',
    })
    let finished = false
    const event = new AfterLoginEvent({ app })
      .fire({ workflowActions: [action], applicationContext: context })
      .then(() => {
        finished = true
      })
    await flushPromises()
    expect(finished).toBe(false)
    release()
    await event
    expect(router.currentRoute.value.path).toBe('/page-sso')
  })

  test('uses next when login has no configured navigation', async () => {
    await new AfterLoginEvent({ app }).fire({
      workflowActions: [],
      applicationContext: context,
    })
    expect(router.currentRoute.value.path).toBe('/original')
  })
  test('a new-tab action also takes precedence over next', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    try {
      const action = populateWorkflowAction({
        id: 1,
        type: 'open_page',
        navigation_type: 'custom',
        navigate_to_url: { formula: "'https://example.com'" },
        target: 'blank',
      })
      await new AfterLoginEvent({ app }).fire({
        workflowActions: [action],
        applicationContext: context,
      })
      expect(open).toHaveBeenCalledWith(
        'https://example.com',
        '_blank',
        'noopener,noreferrer'
      )
      expect(router.currentRoute.value.path).toBe('/login')
    } finally {
      open.mockRestore()
    }
  })

  test.each([
    '//example.com',
    '/\\example.com',
    '%invalid',
    'https://example.com',
  ])('does not follow an unsafe next destination: %s', async (next) => {
    await router.push({ path: '/login', query: { next } })
    await new AfterLoginEvent({ app }).fire({
      workflowActions: [],
      applicationContext: context,
    })
    expect(router.currentRoute.value.path).toBe('/login')
  })
  test('an explicit same-page destination takes precedence over next', async () => {
    const action = populateWorkflowAction({
      id: 1,
      type: 'open_page',
      navigation_type: 'custom',
      navigate_to_url: { formula: "'/login?next=%252Foriginal'" },
      target: 'self',
    })
    await new AfterLoginEvent({ app }).fire({
      workflowActions: [action],
      applicationContext: context,
    })
    expect(router.currentRoute.value.fullPath).toBe('/login?next=%252Foriginal')
  })
})
