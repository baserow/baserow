import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { Suspense, defineComponent, h, withDirectives } from 'vue'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { TestApp } from '@baserow/test/helpers/testApp'
import Sidebar from '@baserow/modules/core/components/sidebar/Sidebar'
import SidebarAllWorkspacesMenu from '@baserow/modules/core/components/sidebar/SidebarAllWorkspacesMenu'
import DatabaseSidebar from '@baserow/modules/database/components/sidebar/Sidebar'
import WorkspacePage from '@baserow/modules/core/pages/workspace'

mockNuxtImport('useRoute', () => () => ({
  params: { workspaceId: '1' },
  query: {},
  matched: [],
}))

const openableStub = (className) =>
  defineComponent({
    data: () => ({ open: false }),
    methods: {
      show() {
        this.open = true
      },
      toggle() {
        this.open = !this.open
      },
    },
    render() {
      return this.open ? h('div', { class: className }) : null
    },
  })

describe('clicks before the page finished loading', () => {
  let testApp

  beforeEach(async () => {
    testApp = new TestApp()
    testApp.authenticate({ id: 1, preferences: {} })
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Design',
    })
    testApp.store.commit('workspace/SET_PERMISSIONS', {
      workspaceId: 1,
      permissions: [],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountBesideLoadingPage = async (component, props, stubs) => {
    let finishLoading
    const pageLoaded = new Promise((resolve) => {
      finishLoading = resolve
    })
    const LoadingPage = defineComponent({
      async setup() {
        await pageLoaded
        return () => h('div')
      },
    })
    let contentElement
    const Layout = defineComponent({
      render: () =>
        h(Suspense, null, {
          default: () =>
            h('div', [
              withDirectives(h('div', [h(component, props)]), [
                [{ created: (el) => (contentElement = el) }],
              ]),
              h(LoadingPage),
            ]),
        }),
    })
    const wrapper = await testApp.mount(Layout, { global: { stubs } })
    await flushPromises()
    return { wrapper, content: new DOMWrapper(contentElement), finishLoading }
  }

  const database = {
    id: 1,
    type: 'database',
    name: 'Sales',
    workspace: { id: 10 },
    _: { loading: false, selected: false },
    tables: [],
  }

  test.each([
    ['sidebar.templates', SidebarAllWorkspacesMenu, {}, 'template-modal-stub'],
    ['sidebar.trash', SidebarAllWorkspacesMenu, {}, 'trash-modal-stub'],
    [
      'sidebar.createTable',
      DatabaseSidebar,
      { application: database, workspace: database.workspace },
      'create-table-modal-stub',
    ],
    ['dashboard.templates', WorkspacePage, {}, 'template-modal-stub'],
    ['dashboard.addNew', WorkspacePage, {}, 'create-context-stub'],
  ])(
    'opens %s clicked before the page finished loading',
    async (linkText, component, props, modalClass) => {
      const { wrapper, content, finishLoading } = await mountBesideLoadingPage(
        component,
        props,
        {
          TemplateModal: openableStub('template-modal-stub'),
          TrashModal: openableStub('trash-modal-stub'),
          CreateTableModal: openableStub('create-table-modal-stub'),
          CreateApplicationContext: openableStub('create-context-stub'),
          RecentlyViewed: true,
          SidebarApplication: {
            template: '<div><slot name="body" /></div>',
          },
        }
      )
      const link = content
        .findAll('a')
        .find((item) => item.text().startsWith(linkText))
      await link.trigger('click')

      finishLoading()
      await flushPromises()

      expect(wrapper.find(`.${modalClass}`).exists()).toBe(true)
    }
  )

  test('opens the workspace switcher clicked before the page finished loading', async () => {
    const workspaces = testApp.store.getters['workspace/getAll']
    const { wrapper, content, finishLoading } = await mountBesideLoadingPage(
      Sidebar,
      { applications: [], workspaces, selectedWorkspace: workspaces[0] },
      {
        SidebarWithWorkspace: true,
        SidebarMenu: true,
        SidebarFoot: true,
        SidebarWorkspacePicker: openableStub('workspace-picker-stub'),
      }
    )
    await content.find('.sidebar__workspace-trigger').trigger('click')

    finishLoading()
    await flushPromises()

    expect(wrapper.find('.workspace-picker-stub').exists()).toBe(true)
  })
})
