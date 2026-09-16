import { getCookieName } from '@baserow/modules/core/utils/cookie'
import { useNuxtApp, useCookie } from '#app'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import AuthFormElement from '@baserow_enterprise/builder/components/elements/AuthFormElement'
import pendingLoginPlugin from '@baserow/modules/builder/plugins/pendingLogin.client'
import PublicPageContent from '@baserow/modules/builder/components/PublicPageContent'
import { populateWorkflowAction } from '@baserow/modules/builder/store/builderWorkflowAction'

describe('SSO After login workflow', () => {
  let wrapper
  let app
  let routerPush

  afterEach(() => {
    wrapper?.unmount()
    window.sessionStorage.clear()
    for (const cookie of document.cookie.split(';')) {
      const name = cookie.split('=')[0].trim()
      if (name.includes('user_source_login_completed_')) {
        document.cookie = `${name}=; Max-Age=0; Path=/`
      }
    }
    vi.restoreAllMocks()
  })

  test.each([
    ['openid_connect', true, 'source-42'],
    ['saml', true, 'source-42'],
    ['openid_connect', false, 'source-42'],
    ['saml', false, 'source-42'],
    ['openid_connect', true, 'other-source'],
    ['saml', true, 'other-source'],
    ['openid_connect', true, 'source-42', true],
    ['saml', true, 'source-42', true],
    ['openid_connect', true, 'source-42', false, false],
    ['saml', true, 'source-42', false, false],
    ['openid_connect', true, 'source-42', false, 'other-attempt'],
    ['saml', true, 'source-42', false, 'other-attempt'],
  ])(
    'resumes only the successful %s login once (authenticated=%s, source=%s)',
    async (
      provider,
      authenticated,
      sourceUid,
      failedCallback = false,
      completed = true
    ) => {
      vi.spyOn(window, 'location', 'get').mockReturnValue(
        new URL('http://localhost/login')
      )
      const leaveForProvider = vi
        .spyOn(window, 'location', 'set')
        .mockImplementation(() => {})
      app = useNuxtApp()
      routerPush = vi.spyOn(app.$router, 'push').mockResolvedValue()
      const page = {
        id: 1,
        path: '/login',
        shared: false,
        graph: {},
        elements: [],
        elementMap: {},
        orderedElements: [],
        query_params: [],
        path_params: [],
        visibility: 'all',
        workflowActions: [],
      }
      const shared = { ...page, id: 2, shared: true, workflowActions: [] }
      const protectedPage = {
        ...page,
        id: 3,
        path: '/page-sso',
        visibility: 'logged-in',
      }
      const element = {
        id: 10,
        page_id: 1,
        type: 'auth_form',
        user_source_id: 42,
        login_button_label: "'Login'",
        styles: {},
        parent_element_id: null,
      }
      const userSource = {
        id: 42,
        uid: 'source-42',
        type: 'local_baserow',
        email_field_id: 1,
        name_field_id: 2,
        auth_providers: [
          { id: 1, type: provider, base_url: 'https://idp.example.com' },
        ],
      }
      const builder = {
        id: 99,
        breakpoints: { mobile: 640, tablet: 1024 },
        theme: {},
        pages: [page, shared, protectedPage],
        user_sources: [userSource],
        login_page_id: 1,
        scripts: [],
        custom_code: { css: '', js: '' },
      }
      page.workflowActions = [
        populateWorkflowAction({
          id: 1,
          element_id: 10,
          page_id: 1,
          event: 'after_login',
          type: 'open_page',
          order: 1,
          navigation_type: 'page',
          navigate_to_page_id: 3,
          page_parameters: [],
          query_parameters: [],
          target: 'self',
        }),
      ]
      wrapper = await mountSuspended(AuthFormElement, {
        props: { element },
        global: {
          provide: {
            workspace: { id: 1 },
            builder,
            currentPage: page,
            elementPage: page,
            mode: 'public',
            applicationContext: { builder, page, element, mode: 'public' },
          },
          stubs: { Modal: true },
        },
      })
      await wrapper.get('button').trigger('click')
      await flushPromises()
      wrapper.unmount()
      const original = new URL(
        new URL(leaveForProvider.mock.calls[0][0]).searchParams.get('original')
      )
      const attemptId = original.searchParams.get('user_source_login_attempt')
      expect(attemptId).toMatch(/^[0-9a-f-]{36}$/)
      // Simulate the receipt issued by the callback bridge, on the clean SSR request.
      if (completed && !failedCallback) {
        app.runWithContext(() => {
          useCookie(
            getCookieName(
              app.$config,
              `user_source_login_completed_${completed === 'other-attempt' ? '00000000-0000-4000-8000-000000000002' : attemptId}`
            )
          ).value = 1
        })
        await flushPromises()
      }

      if (failedCallback) {
        const errorParam =
          provider === 'saml' ? 'saml_error__42' : 'oidc_error__42'
        vi.spyOn(window, 'location', 'get').mockReturnValue(
          new URL(
            `http://localhost/login?${errorParam}=ERROR_INVALID_CREDENTIALS`
          )
        )
        // The plugin clears failed attempts before the page consumes the error;
        // a later authenticated visit must not replay this login.
        await pendingLoginPlugin(app)
        vi.spyOn(window, 'location', 'get').mockReturnValue(
          new URL('http://localhost/login')
        )
      }

      // The clean SSR response is already authenticated. The logged-out form and
      // its actions need not be in the published, permission-filtered response.
      builder.userSourceUser = {
        authenticated,
        user: { user_source_uid: sourceUid },
      }
      page.workflowActions = []
      const mountPage = () =>
        mountSuspended(PublicPageContent, {
          props: {
            workspace: { id: 1 },
            builder,
            page,
            params: {},
            path: '/login',
            mode: 'public',
          },
          global: {
            stubs: {
              BuilderToasts: true,
              PageContent: true,
              RecursiveWrapper: { template: '<div><slot /></div>' },
            },
          },
        })
      wrapper = await mountPage()
      await flushPromises()
      const navigationCount =
        authenticated &&
        sourceUid === 'source-42' &&
        !failedCallback &&
        completed === true
          ? 1
          : 0
      if (navigationCount) {
        expect(routerPush).toHaveBeenCalledWith('/page-sso')
      }
      expect(routerPush).toHaveBeenCalledTimes(navigationCount)
      wrapper.unmount()
      builder.userSourceUser = {
        authenticated: true,
        user: { user_source_uid: 'source-42' },
      }
      wrapper = await mountPage()
      await flushPromises()
      expect(routerPush).toHaveBeenCalledTimes(navigationCount)
    }
  )
})
