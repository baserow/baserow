// @vitest-environment happy-dom
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { h, nextTick } from 'vue'
import { createStore } from 'vuex'
import { Registry } from '@baserow/modules/core/registry'
import CreateWidgetCard from '@baserow/modules/dashboard/components/CreateWidgetCard'
import BuilderSettingsModal from '@baserow/modules/builder/components/settings/BuilderSettingsModal'
import { ChartWidgetType } from '@baserow_premium/dashboard/widgetTypes'
import { CustomCodeBuilderSettingType } from '@baserow_enterprise/builderSettingTypes'
import DomainForm from '@baserow/modules/builder/components/domain/DomainForm'
import {
  CustomDomainType,
  SubDomainType,
} from '@baserow/modules/builder/domainTypes'
import ThemeSettings from '@baserow/modules/builder/components/settings/ThemeSettings'
import {
  ColorThemeConfigBlockType,
  ButtonThemeConfigBlockType,
} from '@baserow/modules/builder/themeConfigBlockTypes'
import Tabs from '@baserow/modules/core/components/Tabs'
import Tab from '@baserow/modules/core/components/Tab'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FormInput from '@baserow/modules/core/components/FormInput'
import FormElement from '@baserow/modules/core/components/FormElement'

const { showPaidFeatures, resetButtonTheme, notifyIf } = vi.hoisted(() => ({
  showPaidFeatures: vi.fn(),
  resetButtonTheme: vi.fn(),
  notifyIf: vi.fn(),
}))

vi.mock('@baserow_premium/components/PaidFeaturesModal', async () => {
  const { h } = await import('vue')
  return {
    default: {
      name: 'PaidFeaturesModal',
      render() {
        return h('div')
      },
      methods: { show: showPaidFeatures },
    },
  }
})

vi.mock('@baserow/modules/core/utils/error', () => ({ notifyIf }))
vi.mock(
  '@baserow/modules/builder/components/theme/ColorThemeConfigBlock',
  async () => {
    const { h } = await import('vue')
    return {
      default: {
        render() {
          return h('button', {
            class: 'change-color',
            onClick: () =>
              this.$emit('values-changed', { primary_color: '#fff' }),
          })
        },
        methods: { reset() {}, isFormValid: () => true },
      },
    }
  }
)
vi.mock(
  '@baserow/modules/builder/components/theme/ButtonThemeConfigBlock',
  async () => {
    const { h } = await import('vue')
    return {
      default: {
        render: () => h('div'),
        methods: { reset: resetButtonTheme, isFormValid: () => true },
      },
    }
  }
)

const Modal = {
  render() {
    return h('div', [this.$slots.sidebar?.(), this.$slots.content?.()])
  },
}
const Button = {
  props: ['disabled'],
  render() {
    return h('button', { disabled: this.disabled }, this.$slots.default?.())
  },
}
const Slot = {
  render() {
    return h('div', this.$slots.default?.())
  },
}
const Dropdown = {
  name: 'Dropdown',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  render() {
    return h('div', this.$slots.default?.())
  },
}

function setupRegistry(namespace, Type) {
  const app = {
    $i18n: { t: (key) => key },
    $hasFeature: () => false,
    $config: { public: { baserowBuilderDomains: ['example.test'] } },
  }
  const registry = new Registry()
  registry.registerNamespace(namespace)
  registry.register(namespace, new Type({ app }))
  return registry
}

describe('registry modals on their first interaction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('opens the paid features modal on the first locked chart click', () => {
    const registry = setupRegistry('dashboardWidget', ChartWidgetType)
    const widgetType = registry.get('dashboardWidget', 'chart')
    const onError = vi.fn()
    const wrapper = mount(CreateWidgetCard, {
      props: {
        dashboard: { workspace: { id: 1 } },
        widgetType,
        variation: widgetType.variations[0],
      },
      global: { config: { errorHandler: onError } },
    })

    wrapper.get('a').element.click()

    expect(showPaidFeatures).toHaveBeenCalledOnce()
    expect(onError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  test('opens the paid features modal on the first locked custom code click', () => {
    const registry = setupRegistry(
      'builderSettings',
      CustomCodeBuilderSettingType
    )
    const onError = vi.fn()
    const wrapper = mount(BuilderSettingsModal, {
      props: { builder: { id: 1 }, workspace: { id: 1 } },
      global: {
        config: { errorHandler: onError },
        mocks: { $registry: registry, $t: (key) => key },
        stubs: { Modal },
        directives: { tooltip: {} },
      },
    })

    wrapper.get('a.modal-sidebar__nav-link').element.click()

    expect(showPaidFeatures).toHaveBeenCalledOnce()
    expect(onError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  test('keeps domain submission safe when switching domain types', async () => {
    const registry = setupRegistry('domain', CustomDomainType)
    registry.register(
      'domain',
      new SubDomainType({ app: registry.get('domain', 'custom').app })
    )
    const create = vi.fn().mockResolvedValue({})
    const store = createStore({
      modules: { domain: { namespaced: true, actions: { create } } },
    })
    const onError = vi.fn()
    const wrapper = mount(DomainForm, {
      props: { builder: { id: 1 }, hideForm: vi.fn() },
      global: {
        plugins: [store],
        components: { FormGroup, FormInput, FormElement },
        config: { errorHandler: onError },
        mocks: { $registry: registry, $t: (key) => key },
        stubs: {
          Button,
          Dropdown,
          DropdownItem: Slot,
          ButtonText: Slot,
          Error: true,
          HelpIcon: true,
        },
      },
    })
    await flushPromises()
    await wrapper.get('input').setValue('custom')
    await wrapper.get('input').setValue('custom.example.test')

    wrapper.getComponent(Dropdown).vm.$emit('update:modelValue', {
      type: 'sub_domain',
      domain: 'example.test',
    })
    await nextTick()
    wrapper.get('button').element.click()

    expect(onError).not.toHaveBeenCalled()
    expect(create).not.toHaveBeenCalled()
    await wrapper.get('input').setValue('new')
    await wrapper.get('input').setValue('new-prefix')
    wrapper.get('button').element.click()
    await flushPromises()
    expect(create).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        type: 'sub_domain',
        domain_name: 'new-prefix.example.test',
      })
    )
    wrapper.unmount()
  })

  test('rolls back and reports a rejected theme update after changing tabs', async () => {
    const registry = setupRegistry(
      'themeConfigBlock',
      ColorThemeConfigBlockType
    )
    registry.register(
      'themeConfigBlock',
      new ButtonThemeConfigBlockType({
        app: registry.get('themeConfigBlock', 'color').app,
      })
    )
    let rejectUpdate
    const request = new Promise((resolve, reject) => {
      rejectUpdate = reject
    })
    const store = createStore({
      modules: {
        theme: { namespaced: true, actions: { setProperty: () => request } },
      },
    })
    const onError = vi.fn()
    const wrapper = mount(ThemeSettings, {
      props: { builder: { id: 1, theme: { primary_color: '#000' } } },
      global: {
        plugins: [store],
        components: { Tabs, Tab },
        config: { errorHandler: onError },
        mocks: { $registry: registry, $t: (key) => key, $router: {} },
        stubs: { ThemeProvider: Slot },
        directives: { tooltip: {} },
      },
    })
    await flushPromises()
    wrapper.get('button.change-color').element.click()
    wrapper.findAll('li.tabs__item')[1].element.click()
    await nextTick()
    const error = new Error('API rejected update')
    rejectUpdate(error)
    await flushPromises()

    expect(onError).not.toHaveBeenCalled()
    expect(resetButtonTheme).toHaveBeenCalledOnce()
    expect(notifyIf).toHaveBeenCalledWith(error, 'application')
    wrapper.unmount()
  })
})
