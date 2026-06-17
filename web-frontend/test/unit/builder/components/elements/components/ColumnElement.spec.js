import ColumnElement from '@baserow/modules/builder/components/elements/components/ColumnElement.vue'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test, describe, beforeEach } from 'vitest'

describe('ColumnElement', () => {
  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = useNuxtApp()
    store = testApp.$store
    if (!store.hasModule('element')) {
      store.registerModule('element', {
        namespaced: true,
        getters: {
          getChildren: () => () => [],
        },
      })
    } else {
      // Override or spy if needed, but since it's a test environment,
      // we can stub it if it is already there.
    }
    await store.dispatch('page/setDeviceTypeSelected', 'desktop')
  })

  const mountComponent = ({ props = {}, slots = {}, provide = {} }) => {
    return mountSuspended(ColumnElement, {
      props,
      slots,
      global: {
        provide,
        mocks: {
          $hasPermission: () => true,
        },
      },
    })
  }

  test('gridTemplateColumns computes correct template for custom layout', async () => {
    const builder = { id: 1, theme: { primary_color: '#ccc' } }
    const page = { orderedElements: [] }
    const workspace = {}
    const element = {
      column_amount: 3,
      column_gap: 30,
      alignment: 'top',
      layout_type: 'custom',
      column_weights: [1, 0, 2],
      column_stacking: {
        smartphone: 'horizontal',
        tablet: 'horizontal',
        desktop: 'horizontal',
      },
    }

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        mode: 'public',
        currentPage: page,
        elementPage: page,
        applicationContext: { builder, page, mode: 'public' },
        element,
        workspace,
      },
    })

    expect(wrapper.vm.gridTemplateColumns).toBe('1fr auto 2fr')
  })

  test('gridTemplateColumns stacks columns depending on the current device', async () => {
    const builder = { id: 1, theme: { primary_color: '#ccc' } }
    const page = { orderedElements: [] }
    const workspace = {}
    const element = {
      column_amount: 3,
      column_gap: 30,
      alignment: 'top',
      layout_type: 'auto',
      column_weights: [],
      column_stacking: {
        smartphone: 'stacked',
        tablet: 'horizontal',
        desktop: 'horizontal',
      },
    }

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        mode: 'public',
        currentPage: page,
        elementPage: page,
        applicationContext: { builder, page, mode: 'public' },
        element,
        workspace,
      },
    })

    await store.dispatch('page/setDeviceTypeSelected', 'desktop')
    expect(wrapper.vm.gridTemplateColumns).toBe('repeat(3, minmax(0, 1fr))')

    await store.dispatch('page/setDeviceTypeSelected', 'tablet')
    expect(wrapper.vm.gridTemplateColumns).toBe('repeat(3, minmax(0, 1fr))')

    await store.dispatch('page/setDeviceTypeSelected', 'smartphone')
    expect(wrapper.vm.gridTemplateColumns).toBe('1fr')
  })

  test('gridTemplateColumns does not stack without explicit opt-in', async () => {
    const builder = { id: 1, theme: { primary_color: '#ccc' } }
    const page = { orderedElements: [] }
    const workspace = {}
    const element = {
      column_amount: 3,
      column_gap: 30,
      alignment: 'top',
      layout_type: 'auto',
      column_weights: [],
      column_stacking: {},
    }

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        mode: 'public',
        currentPage: page,
        elementPage: page,
        applicationContext: { builder, page, mode: 'public' },
        element,
        workspace,
      },
    })

    await store.dispatch('page/setDeviceTypeSelected', 'smartphone')
    expect(wrapper.vm.gridTemplateColumns).toBe('repeat(3, minmax(0, 1fr))')
  })
})
