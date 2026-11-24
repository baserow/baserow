import { inject } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { vi } from 'vitest'

import Dashboard from '@baserow/modules/dashboard/components/Dashboard'

const widgetVariation = {
  type: {
    getType: () => 'summary',
  },
  params: {
    some_parameter: 'value',
  },
}

const DashboardHeaderStub = {
  name: 'DashboardHeader',
  props: ['isCreatingWidget'],
  emits: ['widget-variation-selected'],
  data: () => ({ widgetVariation }),
  template: `
    <button
      data-testid="header-create-widget"
      :data-loading="isCreatingWidget"
      @click="$emit('widget-variation-selected', widgetVariation)"
    >
      Create from header
    </button>
  `,
}

const DashboardContentStub = {
  name: 'DashboardContent',
  props: ['isCreatingWidget'],
  emits: ['widget-variation-selected'],
  data: () => ({ widgetVariation }),
  template: `
    <button
      data-testid="content-create-widget"
      :data-loading="isCreatingWidget"
      @click="$emit('widget-variation-selected', widgetVariation)"
    >
      Create from content
    </button>
  `,
}

describe('Dashboard', () => {
  test('shares the creation state and prevents duplicate widget creation', async () => {
    let resolveCreateWidget
    const dispatch = vi.fn((action) => {
      if (action === 'dashboardApplication/createWidget') {
        return new Promise((resolve) => {
          resolveCreateWidget = resolve
        })
      }

      return Promise.resolve()
    })
    const registry = {
      get: vi.fn().mockReturnValue({
        ...widgetVariation.type,
        name: 'Summary',
        initialGridSize: { width: 2, height: 4 },
      }),
    }
    const wrapper = mount(Dashboard, {
      props: {
        dashboard: { id: 1 },
        loading: false,
      },
      global: {
        mocks: {
          $registry: registry,
          $store: { dispatch, getters: {} },
        },
        stubs: {
          DashboardHeader: DashboardHeaderStub,
          DashboardContent: DashboardContentStub,
        },
      },
    })

    await wrapper.get('[data-testid="header-create-widget"]').trigger('click')

    expect(dispatch).toHaveBeenNthCalledWith(
      1,
      'dashboardApplication/enterEditMode'
    )
    expect(dispatch).toHaveBeenNthCalledWith(
      2,
      'dashboardApplication/createWidget',
      {
        dashboard: { id: 1 },
        onCreated: expect.any(Function),
        select: true,
        widget: {
          title: 'Summary',
          type: 'summary',
          some_parameter: 'value',
        },
      }
    )
    expect(
      wrapper
        .get('[data-testid="header-create-widget"]')
        .attributes('data-loading')
    ).toBe('true')
    expect(
      wrapper
        .get('[data-testid="content-create-widget"]')
        .attributes('data-loading')
    ).toBe('true')

    await wrapper.get('[data-testid="content-create-widget"]').trigger('click')

    expect(dispatch).toHaveBeenCalledTimes(2)

    resolveCreateWidget()
    await flushPromises()

    expect(
      wrapper
        .get('[data-testid="header-create-widget"]')
        .attributes('data-loading')
    ).toBe('false')
    wrapper.unmount()
  })
})

test('provides the dashboard store prefix reactively to descendants', async () => {
  const prefixConsumer = {
    setup() {
      return { storePrefix: inject('storePrefix') }
    },
    template: '<span data-testid="injected-prefix">{{ storePrefix }}</span>',
  }
  const wrapper = mount(Dashboard, {
    props: { dashboard: { id: 1 }, loading: false, storePrefix: 'template/' },
    global: {
      stubs: { DashboardHeader: true, DashboardContent: prefixConsumer },
    },
  })
  expect(wrapper.get('[data-testid="injected-prefix"]').text()).toBe(
    'template/'
  )
  await wrapper.setProps({ storePrefix: '' })
  expect(wrapper.get('[data-testid="injected-prefix"]').text()).toBe('')
  wrapper.unmount()
})
