import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { reactive, ref } from 'vue'

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
  props: ['colNum', 'isDraggable', 'isResizable'],
  emits: ['layout-ready', 'layout-updated'],
  template: `
    <div
      class="vgl-layout"
      :data-columns="colNum"
      :data-draggable="isDraggable"
      :data-resizable="isResizable"
    ><slot /></div>
  `,
}

const GridItemStub = {
  name: 'GridItem',
  props: ['isDraggable', 'isResizable'],
  emits: ['move', 'resize'],
  template: `
    <div
      class="vgl-item"
      :data-draggable="isDraggable"
      :data-resizable="isResizable"
    ><slot /></div>
  `,
}

const DashboardWidgetStub = {
  name: 'DashboardWidget',
  props: ['widget'],
  template:
    '<article class="dashboard-widget-stub">{{ widget.title }}</article>',
}

describe('DashboardWidgetGrid', () => {
  let originalResizeObserver
  let animationFrames
  let resizeObservers
  let wrapper
  let dispatch

  beforeEach(() => {
    animationFrames = []
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
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn((callback) => {
        animationFrames.push(callback)
        return animationFrames.length
      })
    )
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
  })

  afterEach(() => {
    wrapper?.unmount()
    document.body.classList.remove('dashboard-widget-grid--resizing')
    if (originalResizeObserver) {
      globalThis.ResizeObserver = originalResizeObserver
    } else {
      delete globalThis.ResizeObserver
    }
    vi.unstubAllGlobals()
  })

  function mountGrid({
    hasPermission = () => true,
    widgetList = widgets,
    editMode = ref(true),
  } = {}) {
    wrapper = mount(DashboardWidgetGrid, {
      props: {
        dashboard: { id: 1, workspace: { id: 1 } },
      },
      global: {
        mocks: {
          $hasPermission: hasPermission,
          $t: (key) => key,
          $store: {
            dispatch,
            getters: {
              'dashboardApplication/getWidgets': widgetList,
              get 'dashboardApplication/isEditMode'() {
                return editMode.value
              },
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

  test('keeps a loader visible until the initial grid layout is ready', async () => {
    mountGrid({ editMode: ref(false) })

    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-loading"]').exists()
    ).toBe(true)
    expect(
      wrapper.get('[data-testid="dashboard-widget-grid-loading"]').text()
    ).toBe('dashboard.widgetsLoading')
    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-bootstrap"]').exists()
    ).toBe(false)
    expect(wrapper.find('.vgl-layout').exists()).toBe(false)

    await measureGrid(700)

    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-loading"]').exists()
    ).toBe(true)
    expect(wrapper.get('.vgl-layout').attributes('data-columns')).toBe('4')

    await wrapper.findComponent(GridLayoutStub).vm.$emit('layout-ready')

    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-loading"]').exists()
    ).toBe(true)

    animationFrames.shift()()
    await wrapper.vm.$nextTick()

    expect(
      wrapper.find('[data-testid="dashboard-widget-grid-loading"]').exists()
    ).toBe(false)
    expect(wrapper.classes('dashboard-widget-grid--layout-ready')).toBe(true)
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

  test.each([
    ['move', [1, 1, 0], [1, 0, 0]],
    ['resize', [1, 4, 3], [1, 4, 2]],
  ])(
    'resumes widget updates after an unchanged %s',
    async (event, away, back) => {
      const widgetList = reactive(widgets.map((widget) => ({ ...widget })))
      mountGrid({ widgetList })
      await measureGrid(1200)
      const grid = wrapper.findComponent(GridLayoutStub)
      const item = wrapper.findComponent(GridItemStub)
      const layout = [{ i: 1, x: 0, y: 0, w: 2, h: 4 }]

      await grid.vm.$emit('layout-updated', layout)
      expect(dispatch).not.toHaveBeenCalled()

      await item.vm.$emit(event, ...away)
      await item.vm.$emit(event, ...back)
      expect(wrapper.classes()).toContain('dashboard-widget-grid--interacting')

      let finishSaving
      dispatch.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishSaving = resolve
          })
      )
      await grid.vm.$emit('layout-updated', layout)
      await grid.vm.$emit('layout-updated', layout)
      expect(dispatch).toHaveBeenCalledTimes(1)
      expect(dispatch).toHaveBeenCalledWith(
        'dashboardApplication/updateWidgetLayout',
        {
          dashboardId: 1,
          layout: [
            { id: 1, grid_x: 0, grid_y: 0, grid_width: 2, grid_height: 4 },
          ],
        }
      )

      widgetList.push({ ...widgets[0], id: 2, grid_x: 2, title: 'New widget' })
      finishSaving()
      await flushPromises()
      expect(wrapper.classes()).not.toContain(
        'dashboard-widget-grid--interacting'
      )
      expect(wrapper.classes()).not.toContain('dashboard-widget-grid--resizing')
      expect(wrapper.get('[data-testid="dashboard-widget-2"]').text()).toBe(
        'New widget'
      )
    }
  )

  test.each([
    ['desktop', 1200, '6'],
    ['tablet', 700, '4'],
    ['mobile', 599, '1'],
  ])(
    'keeps %s layouts responsive and read-only in view mode',
    async (_viewport, width, columns) => {
      mountGrid({ editMode: ref(false) })
      await measureGrid(width)

      const gridLayout = wrapper.get('.vgl-layout')
      const gridItem = wrapper.get('.vgl-item')

      expect(gridLayout.attributes('data-columns')).toBe(columns)
      expect(gridLayout.attributes('data-draggable')).toBe('false')
      expect(gridLayout.attributes('data-resizable')).toBe('false')
      expect(gridItem.attributes('data-draggable')).toBe('false')
      expect(gridItem.attributes('data-resizable')).toBe('false')
    }
  )

  test.each([700, 599])(
    'edits canonical coordinates when the available width is %s',
    async (width) => {
      mountGrid({ widgetList: [{ ...widgets[0], grid_x: 2, grid_width: 4 }] })
      await measureGrid(width)

      const grid = wrapper.get('.vgl-layout')
      const item = wrapper.get('.vgl-item')
      expect(grid.attributes('data-columns')).toBe('6')
      expect(grid.attributes('data-draggable')).toBe('true')
      expect(grid.attributes('data-resizable')).toBe('true')
      expect(item.attributes()).toMatchObject({
        x: '2',
        w: '4',
        'data-draggable': 'true',
        'data-resizable': 'true',
      })
    }
  )

  test('switches between viewing and editing without saving projected coordinates', async () => {
    const editMode = ref(false)
    mountGrid({
      editMode,
      widgetList: [{ ...widgets[0], grid_x: 2, grid_width: 4 }],
    })
    await measureGrid(700)
    expect(wrapper.get('.vgl-layout').attributes('data-columns')).toBe('4')
    expect(wrapper.get('.vgl-item').attributes('w')).toBe('3')

    editMode.value = true
    await flushPromises()
    expect(wrapper.get('.vgl-layout').attributes('data-columns')).toBe('6')
    expect(wrapper.get('.vgl-item').attributes()).toMatchObject({
      x: '2',
      w: '4',
    })
    await measureGrid(500)
    expect(wrapper.get('.vgl-item').attributes()).toMatchObject({
      x: '2',
      w: '4',
    })

    editMode.value = false
    await flushPromises()
    expect(wrapper.get('.vgl-layout').attributes('data-columns')).toBe('1')
    expect(wrapper.get('.vgl-item').attributes()).toMatchObject({
      x: '0',
      w: '1',
    })
    await wrapper
      .findComponent(GridLayoutStub)
      .vm.$emit('layout-updated', [{ i: 1, x: 0, y: 0, w: 1, h: 4 }])
    expect(dispatch).not.toHaveBeenCalled()
  })

  test('requires layout-update permission on small screens', async () => {
    mountGrid({ hasPermission: () => false })
    await measureGrid(500)
    expect(wrapper.get('.vgl-layout').attributes('data-draggable')).toBe(
      'false'
    )
    expect(wrapper.get('.vgl-item').attributes('data-resizable')).toBe('false')
    await wrapper.findComponent(GridItemStub).vm.$emit('move', 1, 1, 0)
    await wrapper
      .findComponent(GridLayoutStub)
      .vm.$emit('layout-updated', [{ i: 1, x: 1, y: 0, w: 2, h: 4 }])
    expect(dispatch).not.toHaveBeenCalled()
  })
})
