import {
  recycleSlots,
  orderSlots,
  mapScrollPosition,
  virtualToRealScrollTop,
  compensateScrollTop,
  MAX_SAFE_SCROLL_HEIGHT,
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

  describe('mapScrollPosition', () => {
    const windowHeight = 500

    test('1:1 mapping when the placeholder is not capped', () => {
      // Small table: virtualHeight < MAX_SAFE_SCROLL_HEIGHT so
      // placeholderHeight == virtualHeight.
      const virtualHeight = 10_000
      const placeholderHeight = virtualHeight

      const atTop = mapScrollPosition(
        0,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(atTop.virtualScrollTop).toBe(0)
      expect(atTop.maxRealScroll).toBe(9_500)
      expect(atTop.maxVirtualScroll).toBe(9_500)

      const atMiddle = mapScrollPosition(
        4_750,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(atMiddle.virtualScrollTop).toBe(4_750)

      const atBottom = mapScrollPosition(
        9_500,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(atBottom.virtualScrollTop).toBe(9_500)
    })

    test('compressed mapping when the placeholder is capped', () => {
      // 1M rows at 33px = 33M virtual, capped at 10M real.
      const virtualHeight = 33_000_000
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT

      const atTop = mapScrollPosition(
        0,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(atTop.virtualScrollTop).toBe(0)

      const atMiddle = mapScrollPosition(
        (placeholderHeight - windowHeight) / 2,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(atMiddle.virtualScrollTop).toBeCloseTo(
        (virtualHeight - windowHeight) / 2,
        0
      )

      const atBottom = mapScrollPosition(
        placeholderHeight - windowHeight,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(atBottom.virtualScrollTop).toBe(virtualHeight - windowHeight)
    })

    test('scrollTop overshoot is clamped to the bottom', () => {
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const virtualHeight = 33_000_000
      const { virtualScrollTop } = mapScrollPosition(
        placeholderHeight * 2,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(virtualScrollTop).toBe(virtualHeight - windowHeight)
    })

    test('negative scrollTop clamps to zero virtualScrollTop', () => {
      // iOS rubber-band / overscroll can briefly surface a negative
      // scrollTop; without the clamp downstream indices go negative.
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const virtualHeight = 33_000_000
      const { virtualScrollTop } = mapScrollPosition(
        -50,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      expect(virtualScrollTop).toBe(0)
    })

    test('empty table produces a zero virtual scroll range', () => {
      const { virtualScrollTop, maxRealScroll, maxVirtualScroll } =
        mapScrollPosition(0, windowHeight, 0, windowHeight)
      expect(virtualScrollTop).toBe(0)
      expect(maxRealScroll).toBe(0)
      expect(maxVirtualScroll).toBe(0)
    })

    test('placeholder smaller than the viewport produces a zero range', () => {
      // Table that doesn't fill the viewport: the element isn't scrollable,
      // so mapScrollPosition should short-circuit to a zero range instead
      // of returning a 1-pixel maxRealScroll.
      const { virtualScrollTop, maxRealScroll, maxVirtualScroll } =
        mapScrollPosition(0, 100, 100, windowHeight)
      expect(virtualScrollTop).toBe(0)
      expect(maxRealScroll).toBe(0)
      expect(maxVirtualScroll).toBe(0)
    })
  })

  describe('virtualToRealScrollTop', () => {
    const windowHeight = 500

    test('is the exact inverse of mapScrollPosition in capped mode', () => {
      const virtualHeight = 33_000_000
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      for (const scrollTop of [
        0,
        1_234_567,
        placeholderHeight / 2,
        placeholderHeight - windowHeight,
      ]) {
        const { virtualScrollTop } = mapScrollPosition(
          scrollTop,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
        const roundTripped = virtualToRealScrollTop(
          virtualScrollTop,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
        expect(roundTripped).toBeCloseTo(scrollTop, 5)
      }
    })

    test('collapses to 1:1 when the placeholder is not capped', () => {
      const virtualHeight = 10_000
      const placeholderHeight = virtualHeight
      expect(
        virtualToRealScrollTop(
          4_750,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(4_750)
    })

    test('returns zero when nothing is scrollable', () => {
      expect(virtualToRealScrollTop(0, 100, 100, windowHeight)).toBe(0)
      expect(virtualToRealScrollTop(0, windowHeight, 0, windowHeight)).toBe(0)
    })

    test('clamps negative and overshoot virtual positions', () => {
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const virtualHeight = 33_000_000
      const maxReal = placeholderHeight - windowHeight
      expect(
        virtualToRealScrollTop(
          -100,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(0)
      expect(
        virtualToRealScrollTop(
          virtualHeight * 2,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(maxReal)
    })
  })

  describe('compensateScrollTop', () => {
    const windowHeight = 500

    test('preserves the virtual position after a row count increase', () => {
      // 1M rows at 33px = 33M virtual, capped at 10M real. User at middle.
      const rowHeight = 33
      const oldCount = 1_000_000
      const oldVirtualHeight = oldCount * rowHeight
      const oldPlaceholder = MAX_SAFE_SCROLL_HEIGHT
      const scrollTop = 5_000_000
      const { virtualScrollTop: lastVirtualScrollTop } = mapScrollPosition(
        scrollTop,
        oldPlaceholder,
        oldVirtualHeight,
        windowHeight
      )

      // Remote user inserts 100 rows.
      const newCount = oldCount + 100
      const newVirtualHeight = newCount * rowHeight

      const newScrollTop = compensateScrollTop(
        lastVirtualScrollTop,
        newVirtualHeight,
        windowHeight
      )

      // The real scrollTop moved so that the virtual position is preserved.
      const { virtualScrollTop: newVirtualScrollTop } = mapScrollPosition(
        newScrollTop,
        Math.min(newVirtualHeight, MAX_SAFE_SCROLL_HEIGHT),
        newVirtualHeight,
        windowHeight
      )
      expect(newVirtualScrollTop).toBeCloseTo(lastVirtualScrollTop, 5)
    })

    test('preserves the virtual position after a window resize', () => {
      const rowHeight = 33
      const count = 1_000_000
      const virtualHeight = count * rowHeight
      const oldWindowHeight = 500
      const scrollTop = 5_000_000

      const { virtualScrollTop: lastVirtualScrollTop } = mapScrollPosition(
        scrollTop,
        MAX_SAFE_SCROLL_HEIGHT,
        virtualHeight,
        oldWindowHeight
      )

      const newWindowHeight = 600
      const newScrollTop = compensateScrollTop(
        lastVirtualScrollTop,
        virtualHeight,
        newWindowHeight
      )

      const { virtualScrollTop: newVirtualScrollTop } = mapScrollPosition(
        newScrollTop,
        MAX_SAFE_SCROLL_HEIGHT,
        virtualHeight,
        newWindowHeight
      )
      expect(newVirtualScrollTop).toBeCloseTo(lastVirtualScrollTop, 5)
    })

    test('clamps to the new maxRealScroll after a bulk delete leaves lastVirtualScrollTop past the new end', () => {
      // User at 32.5M virtual in a 33M-virtual table (capped at 10M real).
      // A bulk delete drops the table to 16.5M virtual — still capped.
      // Without clamping, the naive ratio yields ≈19.7M real, which the
      // browser silently clamps to ~10M while the store would retain the
      // unclamped value, desyncing DOM and store.
      const lastVirtualScrollTop = 32_500_000
      const newVirtualHeight = 16_500_000
      const newPlaceholder = Math.min(newVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const maxReal = newPlaceholder - windowHeight

      const newScrollTop = compensateScrollTop(
        lastVirtualScrollTop,
        newVirtualHeight,
        windowHeight
      )
      expect(newScrollTop).toBeLessThanOrEqual(maxReal)
      expect(newScrollTop).toBe(maxReal)
    })

    test('collapses to a 1:1 identity when the new virtual height is below the cap', () => {
      // Small table: compensation should just return the virtual position
      // unchanged (which itself equals the real scrollTop in 1:1 mode).
      const virtualHeight = 10_000
      const lastVirtualScrollTop = 4_750
      expect(
        compensateScrollTop(lastVirtualScrollTop, virtualHeight, windowHeight)
      ).toBe(4_750)
    })
  })

  describe('scroll-to-cell target computation (regression guard for GridView.scrollToElementRect)', () => {
    // The vertical branch of `scrollToElementRect` computes a target scroll
    // position by converting the cell's viewport-relative position into
    // virtual space (`virtualScrollTop + elementBottom`), adjusting in
    // virtual space, and then inverse-mapping via `virtualToRealScrollTop`.
    // These tests guard against regressing back to the old real-pixel form,
    // which overshoots by factor S in capped mode.
    const windowHeight = 500
    const rowHeight = 33

    test('capped mode: scrolling a cell 20 px below viewport brings its bottom to viewport_height - 20 (no overshoot)', () => {
      // 1M rows: capped mode with S ≈ 3.3.
      const count = 1_000_000
      const virtualHeight = count * rowHeight
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      // User mid-scroll: real scrollTop = 5M.
      const currentScrollTop = 5_000_000
      const { virtualScrollTop: currentVirtual } = mapScrollPosition(
        currentScrollTop,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      // Cell is 20 px below the viewport bottom: elementBottom = windowHeight + 20.
      const elementBottom = windowHeight + 20
      // scrollToElementRect's new math:
      const targetVirtual = currentVirtual + elementBottom - windowHeight + 20
      const targetReal = virtualToRealScrollTop(
        targetVirtual,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      // After applying, verify the cell's bottom lands at windowHeight - 20
      // in the post-scroll viewport. Cell's absolute virtual bottom stays at
      // (currentVirtual + elementBottom), and the new virtualScrollTop is:
      const { virtualScrollTop: newVirtual } = mapScrollPosition(
        targetReal,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      const cellBottomVirtual = currentVirtual + elementBottom
      const newCellBottomViewport = cellBottomVirtual - newVirtual
      expect(newCellBottomViewport).toBeCloseTo(windowHeight - 20, 0)
    })

    test('capped mode: old real-pixel form (currentScrollTop + elementBottom - windowHeight + 20) WOULD have overshot', () => {
      // Sanity check that documents why the fix matters — if we'd used the
      // real-pixel form, the cell's post-scroll viewport position would be
      // driven ~S px further than it should be.
      const count = 1_000_000
      const virtualHeight = count * rowHeight
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const currentScrollTop = 5_000_000
      const elementBottom = windowHeight + 20
      // Old buggy formula:
      const oldTargetScrollTop =
        currentScrollTop + elementBottom - windowHeight + 20
      const { virtualScrollTop: currentVirtual } = mapScrollPosition(
        currentScrollTop,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      const cellBottomVirtual = currentVirtual + elementBottom
      const { virtualScrollTop: oldNewVirtual } = mapScrollPosition(
        oldTargetScrollTop,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      const oldNewCellBottomViewport = cellBottomVirtual - oldNewVirtual
      // With S ≈ 3.3 and a 40 px real delta, the cell overshoots by ~132 px
      // — i.e. it lands far inside the viewport, nowhere near the intended
      // 20 px margin.
      expect(oldNewCellBottomViewport).toBeLessThan(windowHeight - 100)
    })

    test('uncapped mode: new formula collapses to the old 1:1 behavior', () => {
      // Small table: mapping is 1:1, so the new virtual-space computation
      // yields the same real scrollTop as the old real-pixel form.
      const count = 100
      const virtualHeight = count * rowHeight
      const placeholderHeight = virtualHeight
      const currentScrollTop = 1000
      const elementBottom = windowHeight + 20
      const { virtualScrollTop: currentVirtual } = mapScrollPosition(
        currentScrollTop,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      const newTargetVirtual =
        currentVirtual + elementBottom - windowHeight + 20
      const newTargetReal = virtualToRealScrollTop(
        newTargetVirtual,
        placeholderHeight,
        virtualHeight,
        windowHeight
      )
      const oldTargetScrollTop =
        currentScrollTop + elementBottom - windowHeight + 20
      expect(newTargetReal).toBeCloseTo(oldTargetScrollTop, 5)
    })
  })
})
