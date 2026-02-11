import {
  recycleSlots,
  orderSlots,
} from '@baserow/modules/database/utils/virtualScrolling'

describe('test virtualScrolling utils', () => {
  test('recycle slots', () => {
    const allRows = [
      { id: 1 },
      { id: 2 },
      { id: 3 },
      { id: 4 },
      { id: 5 },
      { id: 6 },
      { id: 7 },
      { id: 8 },
      null,
      null,
      null,
      null,
      null,
      null,
      null,
      null,
      { id: 17 },
      { id: 18 },
      { id: 19 },
      { id: 20 },
      null,
      null,
      null,
      null,
    ]

    const getRowsAndPosition = (offset, limit) => {
      const getPosition = (row, position) => {
        return { top: position + offset }
      }
      return [allRows.slice(offset, offset + limit), getPosition]
    }

    // First confirm whether the testing code works.
    let slots = []
    recycleSlots(slots, ...getRowsAndPosition(2, 4))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 2 }, item: { id: 3 } },
      { id: 1, position: { top: 3 }, item: { id: 4 } },
      { id: 2, position: { top: 4 }, item: { id: 5 } },
      { id: 3, position: { top: 5 }, item: { id: 6 } },
    ])

    slots = []
    recycleSlots(slots, ...getRowsAndPosition(0, 4))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 0 }, item: { id: 1 } },
      { id: 1, position: { top: 1 }, item: { id: 2 } },
      { id: 2, position: { top: 2 }, item: { id: 3 } },
      { id: 3, position: { top: 3 }, item: { id: 4 } },
    ])

    slots[4] = { id: 4, position: {}, item: undefined }
    slots[5] = { id: 5, position: {}, item: undefined }
    recycleSlots(slots, ...getRowsAndPosition(2, 4))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 4 }, item: { id: 5 } },
      { id: 1, position: { top: 5 }, item: { id: 6 } },
      { id: 2, position: { top: 2 }, item: { id: 3 } },
      { id: 3, position: { top: 3 }, item: { id: 4 } },
    ])

    recycleSlots(slots, ...getRowsAndPosition(5, 4))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 6 }, item: { id: 7 } },
      { id: 1, position: { top: 5 }, item: { id: 6 } },
      { id: 2, position: { top: 7 }, item: { id: 8 } },
      { id: 3, position: { top: 8 }, item: null },
    ])

    recycleSlots(slots, ...getRowsAndPosition(7, 5))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 8 }, item: null },
      { id: 1, position: { top: 9 }, item: null },
      { id: 2, position: { top: 7 }, item: { id: 8 } },
      { id: 3, position: { top: 10 }, item: null },
      { id: 4, position: { top: 11 }, item: null },
    ])

    recycleSlots(slots, ...getRowsAndPosition(8, 5))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 8 }, item: null },
      { id: 1, position: { top: 9 }, item: null },
      { id: 2, position: { top: 10 }, item: null },
      { id: 3, position: { top: 11 }, item: null },
      { id: 4, position: { top: 12 }, item: null },
    ])

    recycleSlots(slots, ...getRowsAndPosition(15, 4), 5)
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 15 }, item: null },
      { id: 1, position: { top: 16 }, item: { id: 17 } },
      { id: 2, position: { top: 17 }, item: { id: 18 } },
      { id: 3, position: { top: 18 }, item: { id: 19 } },
      { id: 4, position: {}, item: undefined },
    ])

    slots.splice(slots.length - 1, 1)
    recycleSlots(slots, ...getRowsAndPosition(18, 4))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 19 }, item: { id: 20 } },
      { id: 1, position: { top: 20 }, item: null },
      { id: 2, position: { top: 21 }, item: null },
      { id: 3, position: { top: 18 }, item: { id: 19 } },
    ])

    recycleSlots(slots, ...getRowsAndPosition(16, 4))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 19 }, item: { id: 20 } },
      { id: 1, position: { top: 16 }, item: { id: 17 } },
      { id: 2, position: { top: 17 }, item: { id: 18 } },
      { id: 3, position: { top: 18 }, item: { id: 19 } },
    ])

    recycleSlots(slots, ...getRowsAndPosition(13, 5))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 13 }, item: null },
      { id: 1, position: { top: 16 }, item: { id: 17 } },
      { id: 2, position: { top: 17 }, item: { id: 18 } },
      { id: 3, position: { top: 14 }, item: null },
      { id: 4, position: { top: 15 }, item: null },
    ])

    recycleSlots(slots, ...getRowsAndPosition(12, 5))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 12 }, item: null },
      { id: 1, position: { top: 16 }, item: { id: 17 } },
      { id: 2, position: { top: 13 }, item: null },
      { id: 3, position: { top: 14 }, item: null },
      { id: 4, position: { top: 15 }, item: null },
    ])

    recycleSlots(slots, ...getRowsAndPosition(12, 5))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 12 }, item: null },
      { id: 1, position: { top: 16 }, item: { id: 17 } },
      { id: 2, position: { top: 13 }, item: null },
      { id: 3, position: { top: 14 }, item: null },
      { id: 4, position: { top: 15 }, item: null },
    ])

    recycleSlots(slots, ...getRowsAndPosition(0, 4))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 0 }, item: { id: 1 } },
      { id: 1, position: { top: 1 }, item: { id: 2 } },
      { id: 2, position: { top: 2 }, item: { id: 3 } },
      { id: 3, position: { top: 3 }, item: { id: 4 } },
    ])

    recycleSlots(slots, ...getRowsAndPosition(1, 5))
    expect(slots).toStrictEqual([
      { id: 0, position: { top: 4 }, item: { id: 5 } },
      { id: 1, position: { top: 1 }, item: { id: 2 } },
      { id: 2, position: { top: 2 }, item: { id: 3 } },
      { id: 3, position: { top: 3 }, item: { id: 4 } },
      { id: 4, position: { top: 5 }, item: { id: 6 } },
    ])
  })

  test('order slots', () => {
    const slots = [
      { id: 0, position: { top: 19 }, item: { id: 20 } },
      { id: 1, position: { top: 20 }, item: null },
      { id: 2, position: { top: 21 }, item: null },
      { id: 3, position: { top: 18 }, item: { id: 19 } },
    ]
    orderSlots(slots, [{ id: 19 }, { id: 20 }, null, null])
    expect(slots).toStrictEqual([
      { id: 3, position: { top: 18 }, item: { id: 19 } },
      { id: 0, position: { top: 19 }, item: { id: 20 } },
      { id: 1, position: { top: 20 }, item: null },
      { id: 2, position: { top: 21 }, item: null },
    ])

    orderSlots(slots, [null, null, { id: 20 }, { id: 19 }])
    expect(slots).toStrictEqual([
      { id: 2, position: { top: 21 }, item: null },
      { id: 1, position: { top: 20 }, item: null },
      { id: 0, position: { top: 19 }, item: { id: 20 } },
      { id: 3, position: { top: 18 }, item: { id: 19 } },
    ])

    orderSlots(slots, [{ id: 19 }, null, { id: 20 }, null])
    expect(slots).toStrictEqual([
      { id: 3, position: { top: 18 }, item: { id: 19 } },
      { id: 2, position: { top: 21 }, item: null },
      { id: 0, position: { top: 19 }, item: { id: 20 } },
      { id: 1, position: { top: 20 }, item: null },
    ])

    slots[0].position = {}
    slots[0].item = undefined
    slots[1].position = {}
    slots[1].item = undefined
    orderSlots(slots, [{ id: 19 }, null, { id: 20 }, null])
    expect(slots).toStrictEqual([
      { id: 3, position: {}, item: undefined },
      { id: 2, position: {}, item: undefined },
      { id: 0, position: { top: 19 }, item: { id: 20 } },
      { id: 1, position: { top: 20 }, item: null },
    ])
  })
})
