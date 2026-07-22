import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import PublicSiteErrorPage from '@baserow/modules/builder/components/PublicSiteErrorPage'
import Button from '@baserow/modules/core/components/Button'

describe('PublicSiteErrorPage', () => {
  const createRouterAndMount = async (pathMatch) => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          name: 'application-builder-page',
          path: '/:pathMatch(.*)*',
          component: { template: '<div />' },
        },
      ],
    })
    await router.push({
      name: 'application-builder-page',
      params: { pathMatch },
    })
    await router.isReady()
    const wrapper = mount(PublicSiteErrorPage, {
      props: {
        error: { statusCode: 404, message: 'Page not found' },
      },
      global: {
        plugins: [router],
        components: { Button },
        mocks: { $t: (key) => key },
        stubs: { Logo: true },
      },
    })
    return { router, wrapper }
  }

  test('the home action links to the root from an encoded slash path', async () => {
    const { router, wrapper } = await createRouterAndMount('/')

    expect(router.currentRoute.value.fullPath).toBe('/%2F')
    expect(wrapper.find('.placeholder__action a').attributes('href')).toBe('/')
    wrapper.unmount()
  })

  test('the home action reloads when already on the home page', async () => {
    const { router, wrapper } = await createRouterAndMount('')
    const go = vi.spyOn(router, 'go').mockImplementation(() => {})

    await wrapper.find('.placeholder__action a').trigger('click')

    expect(router.currentRoute.value.path).toBe('/')
    expect(go).toHaveBeenCalledWith(0)
    wrapper.unmount()
  })

  test('the close tab action replaces home navigation when requested', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          name: 'application-builder-preview',
          path: '/builder-preview/:pathMatch(.*)*',
          component: { template: '<div />' },
        },
      ],
    })
    await router.push({
      name: 'application-builder-preview',
      params: { pathMatch: '' },
    })
    await router.isReady()
    const close = vi.spyOn(window, 'close').mockImplementation(() => {})
    const wrapper = mount(PublicSiteErrorPage, {
      props: {
        error: {
          statusCode: 401,
          message: 'Preview session expired',
          data: { closeTab: true },
        },
      },
      global: {
        plugins: [router],
        components: { Button },
        mocks: { $t: (key) => key },
        stubs: { Logo: true },
      },
    })

    expect(wrapper.find('.placeholder__action').text()).toBe('action.close')
    expect(wrapper.find('.placeholder__action a').exists()).toBe(false)
    await wrapper.find('.placeholder__action button').trigger('click')
    expect(close).toHaveBeenCalledOnce()
    wrapper.unmount()
    close.mockRestore()
  })
})
