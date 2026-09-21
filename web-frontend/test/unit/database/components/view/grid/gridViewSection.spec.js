import { h, nextTick, ref } from 'vue'
import flushPromises from 'flush-promises'

import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewSection from '@baserow/modules/database/components/view/grid/GridViewSection'
import { fitGroupByWidths } from '@baserow/modules/database/utils/gridGroupByWidths'
import { GRID_VIEW_MIN_FIELD_WIDTH } from '@baserow/modules/database/constants'

describe('GridViewSection group column resizing', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    window.dispatchEvent(new MouseEvent('mouseup'))
    await testApp.afterEach()
  })

  const mountSection = async () => {
    const availableWidth = ref(250)
    const groupBy = {
      id: 10,
      view: 1,
      field: 1,
      order: 'ASC',
      type: 'default',
      width: 200,
      _: { loading: false },
    }
    const view = { id: 1, group_bys: [groupBy], group_by_layout: 'column' }
    await testApp.store.dispatch('page/view/grid/updateActiveGroupBys', [
      groupBy,
    ])
    testApp.mock.onPatch('/database/views/group_by/10/').reply(200, {})

    const wrapper = await testApp.mount(
      {
        render() {
          return h(GridViewSection, {
            view,
            database: { id: 1, workspace: { id: 1 } },
            table: { id: 1 },
            visibleFields: [],
            allVisibleFields: [],
            allFieldsInTable: [],
            decorationsByPlace: {},
            includeGroupBy: true,
            readOnly: false,
            storePrefix: 'page/',
            groupByWidths: fitGroupByWidths(
              testApp.store.getters['page/view/grid/getActiveGroupBys'],
              availableWidth.value,
              GRID_VIEW_MIN_FIELD_WIDTH
            ),
          })
        },
      },
      {
        global: {
          mocks: { $hasPermission: () => true },
          stubs: {
            GridViewHead: true,
            GridViewGroupByColumns: true,
            GridViewGroupByRows: true,
          },
        },
      }
    )
    return { wrapper, availableWidth }
  }

  const moveMouse = async (type, clientX) => {
    window.dispatchEvent(new MouseEvent(type, { clientX }))
    await nextTick()
  }

  test.each([
    { positions: [240] },
    { positions: [270] },
    { positions: [270, 240] },
  ])(
    'persists the final width after dragging through $positions',
    async ({ positions }) => {
      const { wrapper, availableWidth } = await mountSection()
      const finalWidth = positions.at(-1)
      await wrapper
        .get('.grid-view__head-group-width-handle')
        .trigger('mousedown', { clientX: 200 })

      for (const position of positions) {
        await moveMouse('mousemove', position)
      }
      expect(
        wrapper.get('.grid-view__group-by-divider').attributes('style')
      ).toContain(`left: ${Math.min(finalWidth, 250)}px`)
      expect(
        wrapper.find('.grid-view__head-group-width-handle.dragging').exists()
      ).toBe(true)
      expect(testApp.mock.history.patch).toHaveLength(0)

      await moveMouse('mouseup', finalWidth)
      await flushPromises()

      expect(testApp.mock.history.patch).toHaveLength(1)
      expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
        width: finalWidth,
      })
      expect(wrapper.find('.grid-view__head-group-width-handle').exists()).toBe(
        finalWidth <= 250
      )

      availableWidth.value = 400
      await nextTick()
      expect(
        wrapper.get('.grid-view__group-by-divider').attributes('style')
      ).toContain(`left: ${finalWidth}px`)
      expect(wrapper.find('.grid-view__head-group-width-handle').exists()).toBe(
        true
      )
    }
  )

  test('finishes a drag returned to its original width without persisting', async () => {
    const { wrapper, availableWidth } = await mountSection()
    await wrapper
      .get('.grid-view__head-group-width-handle')
      .trigger('mousedown', { clientX: 200 })

    await moveMouse('mousemove', 270)
    await moveMouse('mousemove', 200)
    await moveMouse('mouseup', 200)
    await flushPromises()

    expect(testApp.mock.history.patch).toHaveLength(0)
    expect(
      wrapper.get('.grid-view__group-by-divider').attributes('style')
    ).toContain('left: 200px')

    availableWidth.value = 150
    await nextTick()
    expect(wrapper.find('.grid-view__head-group-width-handle').exists()).toBe(
      false
    )
  })
})
