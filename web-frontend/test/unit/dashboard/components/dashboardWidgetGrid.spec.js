import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import DashboardWidgetGrid from '@baserow/modules/dashboard/components/DashboardWidgetGrid.client'

const widgets = [
  {
    id: 1,
    type: 'summary',
    title: 'Summary',
    grid_x: 0,
    grid_y: 0,
    grid_width: 2,
    grid_height: 4,
  },
]

const GridLayoutStub = {
  name: 'GridLayout',
  props: ['colNum'],
  template: '<div class="vgl-layout" :data-columns="colNum"><slot /></div>',
}

const GridItemStub = {
  name: 'GridItem',
  template: '<div class="vgl-item"><slot /></div>',
}

const DashboardWidgetStub = {
  name: 'DashboardWidget',
  props: ['widget'],
  template:
    '<article class="dashboard-widget-stub">{{ widget.title }}</article>',
}

describe('DashboardWidgetGrid', () => {
  let originalResizeObserver
  let resizeObservers
  let wrapper
  let dispatch

  beforeEach(() => {
    resizeObservers = []
    dispatch = vi.fn().mockResolvedValue()
    originalResizeObserver = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      constructor(callback) {
        this.callback = callback
        resizeObservers.push(this)
      }

      disconnect = vi.fn()

      observe = vi.fn()
    }
  })

  afterEach(() => {
    wrapper?.unmount()
    document.body.classList.remove('dashboard-widget-grid--resizing')
    if (originalResizeObserver) {
      globalThis.ResizeObserver = originalResizeObserver
    } else {
      delete globalThis.ResizeObserver
    }
  })

  function mountGrid({ hasPermission = () => true } = {}) {
    wrapper = mount(DashboardWidgetGrid, {
      props: {
        dashboard: { id: 1, workspace: { id: 1 } },
      },
      global: {
        mocks: {
          $hasPermission: hasPermission,
          $store: {
            dispatch,
            getters: {
              'dashboardApplication/getWidgets': widgets,
              'dashboardApplication/isEditMode': true,
            },
          },
        },
        stubs: {
          DashboardWidget: DashboardWidgetStub,
          GridItem: GridItemStub,
          GridLayout: GridLayoutStub,
        },
      },
    })

    return wrapper
  }

  async function measureGrid(width) {
    await wrapper.vm.$nextTick()
    const observer = resizeObservers.at(-1)
    observer.callback([
      {
        target: wrapper.element,
        contentRect: { width, height: 600 },
      },
    ])
    await wrapper.vm.$nextTick()
  }

  test('waits for its measured width before mounting the interactive grid', async () => {
    mountGrid()

    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-bootstrap"]').exists()
    ).toBe(true)
    expect(wrapper.find('.vgl-layout').exists()).toBe(false)

    await measureGrid(700)

    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-bootstrap"]').exists()
    ).toBe(false)
    expect(wrapper.get('.vgl-layout').attributes('data-columns')).toBe('4')
  })

  test('cleans up the resize cursor when a pointer operation ends outside a grid item', async () => {
    mountGrid()
    await measureGrid(1200)

    for (const eventName of ['pointerup', 'pointercancel', 'blur']) {
      wrapper.vm.startResize(
        { i: 1, w: 2, h: 4 },
        { target: { closest: () => true } }
      )
      expect(
        document.body.classList.contains('dashboard-widget-grid--resizing')
      ).toBe(true)

      window.dispatchEvent(new Event(eventName))
      expect(
        document.body.classList.contains('dashboard-widget-grid--resizing')
      ).toBe(false)
    }
  })

  test('allows deletion without layout-update permission', async () => {
    mountGrid({
      hasPermission: (permission) => permission === 'dashboard.widget.delete',
    })
    await measureGrid(1200)

    await wrapper.vm.deleteWidget(1)

    expect(dispatch).toHaveBeenCalledWith(
      'dashboardApplication/deleteWidget',
      1
    )
  })
})
