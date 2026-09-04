import workflowActionStore from '@baserow/modules/builder/store/builderWorkflowAction'

describe('builderWorkflowAction store', () => {
  describe('ORDER_ITEMS', () => {
    test("reordering one element's actions leaves another element's untouched", () => {
      // Regression: reordering the actions of one element used to reset every other
      // element's actions to order 0 (they fell into the `index === -1` branch),
      // reshuffling them. The reorder must be scoped to the targeted element.
      const page = {
        workflowActions: [
          { id: 1, element_id: 10, order: 1 },
          { id: 2, element_id: 10, order: 2 },
          { id: 3, element_id: 20, order: 1 },
          { id: 4, element_id: 20, order: 2 },
        ],
      }

      // Reorder element 10's actions to [2, 1].
      workflowActionStore.mutations.ORDER_ITEMS(
        {},
        { page, order: [2, 1], elementId: 10 }
      )

      const orderById = Object.fromEntries(
        page.workflowActions.map((w) => [w.id, w.order])
      )
      // Element 10's actions are reordered...
      expect(orderById[2]).toBe(1)
      expect(orderById[1]).toBe(2)
      // ...while element 20's actions keep their original order.
      expect(orderById[3]).toBe(1)
      expect(orderById[4]).toBe(2)
    })

    test('without an elementId, every action on the page is reordered', () => {
      const page = {
        workflowActions: [
          { id: 1, element_id: 10, order: 1 },
          { id: 2, element_id: 10, order: 2 },
        ],
      }

      workflowActionStore.mutations.ORDER_ITEMS({}, { page, order: [2, 1] })

      const orderById = Object.fromEntries(
        page.workflowActions.map((w) => [w.id, w.order])
      )
      expect(orderById[2]).toBe(1)
      expect(orderById[1]).toBe(2)
    })
  })
})
