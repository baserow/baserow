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
      get: vi.fn().mockReturnValue({ name: 'Summary' }),
    }
    const wrapper = mount(Dashboard, {
      props: {
        dashboard: { id: 1 },
      },
      global: {
        mocks: {
          $registry: registry,
          $store: { dispatch },
        },
        stubs: {
          DashboardHeader: DashboardHeaderStub,
          DashboardContent: DashboardContentStub,
        },
      },
    })

    await wrapper.get('[data-testid="header-create-widget"]').trigger('click')

    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/createWidget', {
      dashboard: { id: 1 },
      widget: {
        title: 'Summary',
        type: 'summary',
        some_parameter: 'value',
      },
    })
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

    expect(dispatch).toHaveBeenCalledTimes(1)

    resolveCreateWidget()
    await flushPromises()

    expect(dispatch).toHaveBeenLastCalledWith(
      'dashboardApplication/enterEditMode'
    )
    expect(
      wrapper
        .get('[data-testid="header-create-widget"]')
        .attributes('data-loading')
    ).toBe('false')
  })
})
