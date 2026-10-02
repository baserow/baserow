import { defineComponent, markRaw } from 'vue'
import flushPromises from 'flush-promises'

import { Registry, Registerable } from '@baserow/modules/core/registry'
import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import BuilderSettingsModal from '@baserow/modules/builder/components/settings/BuilderSettingsModal'
import AutomationSettingsModal from '@baserow/modules/automation/components/settings/AutomationSettingsModal'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import DatabaseSidebar from '@baserow/modules/database/components/sidebar/Sidebar'
import { TestApp } from '@baserow/test/helpers/testApp'

const SettingComponent = markRaw(
  defineComponent({ template: '<p>Loaded settings form</p>' })
)

const TemplatePage = markRaw(
  defineComponent({
    props: ['pageValue'],
    template: '<p>Loaded template page {{ pageValue.name }}</p>',
  })
)

class PreviewApplicationType extends ApplicationType {
  static getType() {
    return 'builder'
  }

  getIconClass() {
    return 'iconoir-test'
  }

  getName() {
    return 'Preview application'
  }

  populate(application) {
    if (!this.app.$registry.isDomainLoaded(this.type)) {
      throw new Error('Domain not ready')
    }
    return application
  }

  getTemplatePage(application) {
    return application
  }

  getTemplatesPageComponent() {
    return TemplatePage
  }
}

class LazySettingType extends Registerable {
  static getType() {
    return 'lazy_test_setting'
  }

  get name() {
    return 'Loaded settings tab'
  }

  get component() {
    return SettingComponent
  }

  isDeactivated() {
    return false
  }

  isDeactivatedReason() {
    return null
  }

  getDeactivatedModal() {
    return null
  }
}

const ModalStub = defineComponent({
  name: 'Modal',
  data: () => ({ open: false }),
  methods: {
    show() {
      this.open = true
    },
  },
  // Render hidden slots too, exercising lists computed before loading finishes.
  template:
    '<section v-show="open"><slot name="sidebar" /><slot name="content" /></section>',
})

describe('settings opened from the workspace sidebar before a domain loads', () => {
  let testApp
  let registry
  let originalSettings
  let namespace

  beforeEach(() => {
    testApp = new TestApp()
    registry = testApp.getRegistry()
  })

  afterEach(async () => {
    if (namespace) {
      for (const type of registry.getList(namespace)) {
        registry.unregister(namespace, type.getType())
      }
      for (const type of originalSettings) {
        registry.register(namespace, type)
      }
    }
    namespace = null
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test.each([
    ['builder', 'builderSettings', BuilderSettingsModal],
    ['automation', 'automationSettings', AutomationSettingsModal],
  ])(
    '%s waits for registrations before opening its settings',
    async (domain, ns, SettingsModal) => {
      namespace = ns
      originalSettings = registry.getList(namespace)
      for (const type of originalSettings) {
        registry.unregister(namespace, type.getType())
      }
      let finishLoading
      const pending = new Promise((resolve) => (finishLoading = resolve))
      const load = vi
        .spyOn(registry, 'loadDomain')
        .mockImplementation((name) => {
          return name === domain ? pending : Promise.resolve()
        })
      if (domain === 'builder') {
        vi.spyOn(
          registry.get('application', 'builder'),
          'loadExtraData'
        ).mockResolvedValue()
      }
      const Host = defineComponent({
        components: { SettingsModal },
        data: () => ({ application: { id: 1 }, workspace: { id: 1 } }),
        template:
          '<button @click="$refs.settings.show(\'lazy_test_setting\')">Open settings</button>' +
          `<SettingsModal ref="settings" :${domain}="application" :workspace="workspace" />`,
      })
      const wrapper = await testApp.mount(Host, {
        global: { stubs: { Modal: ModalStub } },
      })

      await wrapper.find('button').trigger('click')
      expect(wrapper.text()).not.toContain('Loaded settings form')
      expect(load).toHaveBeenCalledWith('database')
      expect(load).toHaveBeenCalledWith(domain)

      registry.register(namespace, new LazySettingType())
      finishLoading()
      await flushPromises()

      expect(wrapper.text()).toContain('Loaded settings tab')
      expect(wrapper.text()).toContain('Loaded settings form')
      expect(wrapper.find('section').isVisible()).toBe(true)
    }
  )
})

describe('standalone template previews', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('clears its loading state and handles a failed domain load', async () => {
    const registry = new Registry()
    const notify = vi.fn()
    vi.spyOn(registry, 'loadDomain').mockRejectedValue({
      handler: { notifyIf: notify },
    })
    testApp.mock
      .onGet('/applications/workspace/1/')
      .reply(200, [
        { id: 1, name: 'Builder', type: 'builder', workspace: { id: 1 } },
      ])

    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template: { workspace_id: 1 } },
      global: {
        mocks: { $registry: registry },
        stubs: { TemplateSidebar: true },
      },
    })

    expect(wrapper.find('.loading-absolute-center').exists()).toBe(false)
    expect(notify).toHaveBeenCalledWith('templates')
    expect(wrapper.text()).not.toContain('Loaded template page')
  })

  test('loads only the template application domains before populating the preview', async () => {
    const registry = new Registry()
    registry.registerNamespace('application')
    registry.register(
      'application',
      new PreviewApplicationType({ app: { $registry: registry } })
    )
    let finishLoading
    registry.registerDomainLoader(
      'builder',
      () =>
        new Promise((resolve) => {
          finishLoading = () => {
            resolve()
          }
        })
    )
    const database = vi.fn()
    const automation = vi.fn()
    registry.registerDomainLoader('database', database)
    registry.registerDomainLoader('automation', automation)
    testApp.mock
      .onGet('/applications/workspace/1/')
      .reply(200, [
        { id: 1, name: 'Builder', type: 'builder', workspace: { id: 1 } },
      ])

    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template: { workspace_id: 1 } },
      global: {
        mocks: { $registry: registry },
        stubs: { TemplateSidebar: true },
      },
    })
    expect(wrapper.find('.loading-absolute-center').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Loaded template page')
    expect(database).toHaveBeenCalledTimes(1)
    expect(automation).not.toHaveBeenCalled()

    finishLoading()
    await flushPromises()
    expect(wrapper.find('.loading-absolute-center').exists()).toBe(false)
    expect(wrapper.text()).toContain('Loaded template page')
  })

  test.each(['resolve', 'reject', 'clear'])(
    'ignores an obsolete template load after %s',
    async (outcome) => {
      const registry = new Registry()
      registry.registerNamespace('application')
      class DatabasePreviewApplicationType extends PreviewApplicationType {
        static getType() {
          return 'database'
        }
      }
      const context = { app: { $registry: registry } }
      registry.register('application', new PreviewApplicationType(context))
      registry.register(
        'application',
        new DatabasePreviewApplicationType(context)
      )
      let finishLoading
      registry.registerDomainLoader(
        'builder',
        () =>
          new Promise((resolve, reject) => {
            finishLoading = outcome === 'reject' ? reject : resolve
          })
      )
      registry.registerDomainLoader('database', vi.fn())
      testApp.mock
        .onGet('/applications/workspace/1/')
        .reply(200, [
          { id: 1, name: 'Old builder', type: 'builder', workspace: { id: 1 } },
        ])
      testApp.mock.onGet('/applications/workspace/2/').reply(200, [
        {
          id: 2,
          name: 'New database',
          type: 'database',
          workspace: { id: 2 },
        },
      ])
      const wrapper = await testApp.mount(TemplatePreview, {
        props: { template: { workspace_id: 1 } },
        global: {
          mocks: { $registry: registry },
          stubs: { TemplateSidebar: true },
        },
      })
      expect(wrapper.find('.loading-absolute-center').exists()).toBe(true)

      await wrapper.setProps({
        template: outcome === 'clear' ? null : { workspace_id: 2 },
      })
      await flushPromises()
      if (outcome !== 'clear') {
        expect(wrapper.text()).toContain('New database')
      }

      finishLoading(
        outcome === 'reject' ? new Error('Stale chunk failed') : undefined
      )
      await flushPromises()
      if (outcome !== 'clear') {
        expect(wrapper.text()).toContain('New database')
      }
      expect(wrapper.text()).not.toContain('Old builder')
      expect(wrapper.find('.loading-absolute-center').exists()).toBe(false)
    }
  )

  test('an older request does not clear the newer template loading spinner', async () => {
    const registry = new Registry()
    registry.registerNamespace('application')
    class AutomationPreviewApplicationType extends PreviewApplicationType {
      static getType() {
        return 'automation'
      }
    }
    const context = { app: { $registry: registry } }
    registry.register('application', new PreviewApplicationType(context))
    registry.register(
      'application',
      new AutomationPreviewApplicationType(context)
    )
    let finishBuilder
    let finishAutomation
    registry.registerDomainLoader(
      'builder',
      () =>
        new Promise((resolve) => {
          finishBuilder = resolve
        })
    )
    registry.registerDomainLoader(
      'automation',
      () =>
        new Promise((resolve) => {
          finishAutomation = resolve
        })
    )
    registry.registerDomainLoader('database', vi.fn())
    testApp.mock
      .onGet('/applications/workspace/1/')
      .reply(200, [
        { id: 1, name: 'Old builder', type: 'builder', workspace: { id: 1 } },
      ])
    testApp.mock.onGet('/applications/workspace/2/').reply(200, [
      {
        id: 2,
        name: 'New automation',
        type: 'automation',
        workspace: { id: 2 },
      },
    ])
    const wrapper = await testApp.mount(TemplatePreview, {
      props: { template: { workspace_id: 1 } },
      global: {
        mocks: { $registry: registry },
        stubs: { TemplateSidebar: true },
      },
    })
    await wrapper.setProps({ template: { workspace_id: 2 } })
    await flushPromises()
    finishBuilder()
    await flushPromises()
    expect(wrapper.find('.loading-absolute-center').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Old builder')

    finishAutomation()
    await flushPromises()
    expect(wrapper.find('.loading-absolute-center').exists()).toBe(false)
    expect(wrapper.text()).toContain('New automation')
  })

  test.each(['empty', 'failed'])(
    'clears the previous page for an %s template preview',
    async (result) => {
      const registry = new Registry()
      registry.registerNamespace('application')
      class DatabasePreviewApplicationType extends PreviewApplicationType {
        static getType() {
          return 'database'
        }
      }
      registry.register(
        'application',
        new DatabasePreviewApplicationType({ app: { $registry: registry } })
      )
      registry.registerDomainLoader('database', vi.fn())
      const notify = vi.fn()
      registry.registerDomainLoader('automation', () =>
        Promise.reject({
          handler: { notifyIf: notify },
        })
      )
      testApp.mock.onGet('/applications/workspace/1/').reply(200, [
        {
          id: 1,
          name: 'Old database',
          type: 'database',
          workspace: { id: 1 },
        },
      ])
      testApp.mock.onGet('/applications/workspace/2/').reply(
        200,
        result === 'empty'
          ? []
          : [
              {
                id: 2,
                name: 'New automation',
                type: 'automation',
                workspace: { id: 2 },
              },
            ]
      )
      const wrapper = await testApp.mount(TemplatePreview, {
        props: { template: { workspace_id: 1 } },
        global: {
          mocks: { $registry: registry },
          stubs: { TemplateSidebar: true },
        },
      })
      expect(wrapper.text()).toContain('Old database')

      await wrapper.setProps({ template: { workspace_id: 2 } })
      await flushPromises()
      expect(wrapper.find('.loading-absolute-center').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('Loaded template page')
      expect(wrapper.text()).not.toContain('Old database')
      if (result === 'failed') {
        expect(notify).toHaveBeenCalledWith('templates')
      }
    }
  )
})

describe('database sidebar domain loading', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountSidebar = (registry, selected = false) => {
    const application = {
      id: 1,
      workspace: { id: 1 },
      tables: [{ id: 2, name: 'Table', order: 1 }],
      _: { selected: false },
    }
    testApp.store.commit('application/SET_ITEMS', [application])
    if (selected) {
      testApp.store.commit('application/SET_SELECTED', application)
    }
    return testApp.mount(DatabaseSidebar, {
      props: { application, workspace: { id: 1 } },
      global: {
        mocks: { $registry: registry, $hasPermission: () => false },
        stubs: {
          SidebarApplication: { template: '<div><slot name="body" /></div>' },
          SidebarItem: {
            props: ['table'],
            template: '<li>{{ table.name }}</li>',
          },
          CreateTableModal: true,
        },
      },
    })
  }

  test('does not load a collapsed application and waits for all extensions when selected', async () => {
    const registry = new Registry()
    const core = vi.fn()
    registry.registerDomainLoader('database', core)
    let finishExtension
    registry.registerDomainLoader(
      'database',
      () =>
        new Promise((resolve) => {
          finishExtension = resolve
        })
    )
    const wrapper = await mountSidebar(registry)
    expect(core).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('Table')

    testApp.store.commit(
      'application/SET_SELECTED',
      testApp.store.getters['application/get'](1)
    )
    await flushPromises()
    expect(core).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('Table')

    finishExtension()
    await flushPromises()
    expect(wrapper.text()).toContain('Table')
  })

  test('renders selected tables immediately when route middleware loaded the domain', async () => {
    const registry = new Registry()
    registry.registerDomainLoader('database', vi.fn())
    await registry.loadDomain('database')

    const wrapper = await mountSidebar(registry, true)
    expect(wrapper.text()).toContain('Table')
  })
})
