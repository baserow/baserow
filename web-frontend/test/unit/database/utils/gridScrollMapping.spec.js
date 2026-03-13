import {
  MAX_SAFE_SCROLL_HEIGHT,
  getMiddleRowIndex,
  realToVirtualScrollTop,
  virtualToRealScrollTop,
  compensateScrollTop,
} from '@baserow/modules/database/utils/gridScrollMapping'

describe('gridScrollMapping', () => {
  describe('realToVirtualScrollTop', () => {
    test('identity mapping when virtualHeight <= placeholderHeight', () => {
      // Small table: 100 rows * 33px = 3300px, well under MAX_SAFE_SCROLL_HEIGHT
      const virtualHeight = 3300
      const placeholderHeight = 3300
      const windowHeight = 600

      expect(
        realToVirtualScrollTop(
          0,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(0)

      expect(
        realToVirtualScrollTop(
          500,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(500)

      const maxScroll = placeholderHeight - windowHeight
      expect(
        realToVirtualScrollTop(
          maxScroll,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(maxScroll)
    })

    test('scaled mapping when virtualHeight > placeholderHeight', () => {
      // Large table: 500000 rows * 33px = 16,500,000px virtual height
      const rowHeight = 33
      const count = 500000
      const virtualHeight = count * rowHeight
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const windowHeight = 600

      const maxRealScroll = placeholderHeight - windowHeight
      const maxVirtualScroll = virtualHeight - windowHeight

      // scrollTop=0 → 0
      expect(
        realToVirtualScrollTop(
          0,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(0)

      // scrollTop=maxRealScroll → maxVirtualScroll
      expect(
        realToVirtualScrollTop(
          maxRealScroll,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(maxVirtualScroll)

      // scrollTop=midpoint → proportional midpoint
      const midReal = maxRealScroll / 2
      const midVirtual = maxVirtualScroll / 2
      expect(
        realToVirtualScrollTop(
          midReal,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBeCloseTo(midVirtual, 5)
    })

    test('edge case: windowHeight >= placeholderHeight (maxRealScroll clamped to 1)', () => {
      const virtualHeight = 500
      const placeholderHeight = 500
      const windowHeight = 600

      // maxRealScroll = max(500-600, 1) = 1, maxVirtualScroll = max(500-600, 0) = 0
      expect(
        realToVirtualScrollTop(
          0,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(0)

      expect(
        realToVirtualScrollTop(
          1,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(0)
    })

    test('edge case: count=0 (virtualHeight=0)', () => {
      const virtualHeight = 0
      const placeholderHeight = 0
      const windowHeight = 600

      expect(
        realToVirtualScrollTop(
          0,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(0)
    })

    test('scrollTop capped at 1 via scrollFraction', () => {
      const virtualHeight = 16500000
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const windowHeight = 600
      const maxRealScroll = placeholderHeight - windowHeight
      const maxVirtualScroll = virtualHeight - windowHeight

      // scrollTop beyond maxRealScroll should cap at maxVirtualScroll
      expect(
        realToVirtualScrollTop(
          maxRealScroll + 1000,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(maxVirtualScroll)
    })
  })

  describe('getMiddleRowIndex', () => {
    test('returns middle row for a small table scrolled to the top', () => {
      const rowHeight = 33
      const count = 100
      const virtualHeight = count * rowHeight // 3300
      const placeholderHeight = virtualHeight
      const windowHeight = 600

      // scrollTop=0: middle = 300, ceil(300/33)-1 = ceil(9.09)-1 = 10-1 = 9
      expect(
        getMiddleRowIndex(
          0,
          placeholderHeight,
          virtualHeight,
          windowHeight,
          rowHeight,
          count
        )
      ).toBe(9)
    })

    test('returns last row index when scrolled to the bottom', () => {
      const rowHeight = 33
      const count = 100
      const virtualHeight = count * rowHeight
      const placeholderHeight = virtualHeight
      const windowHeight = 600
      const maxScroll = placeholderHeight - windowHeight // 2700

      // scrollTop=2700: middle = 3000, ceil(3000/33)-1 = ceil(90.9)-1 = 91-1 = 90
      expect(
        getMiddleRowIndex(
          maxScroll,
          placeholderHeight,
          virtualHeight,
          windowHeight,
          rowHeight,
          count
        )
      ).toBe(90)
    })

    test('works with scaled mapping for large tables', () => {
      const rowHeight = 33
      const count = 500000
      const virtualHeight = count * rowHeight
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const windowHeight = 600

      // At scrollTop=0, middle row should be near the top
      const topIndex = getMiddleRowIndex(
        0,
        placeholderHeight,
        virtualHeight,
        windowHeight,
        rowHeight,
        count
      )
      expect(topIndex).toBe(9)

      // At max scroll, the middle of the window is near the end but not at
      // the very last row (since it's the window center, not the bottom edge).
      const maxScroll = placeholderHeight - windowHeight
      const bottomIndex = getMiddleRowIndex(
        maxScroll,
        placeholderHeight,
        virtualHeight,
        windowHeight,
        rowHeight,
        count
      )
      // middle = (virtualHeight - windowHeight) + windowHeight/2 = virtualHeight - 300
      // ceil((16500000 - 300) / 33) - 1 = 499990
      expect(bottomIndex).toBe(499990)
    })

    test('returns 0 when count is 0', () => {
      expect(getMiddleRowIndex(0, 0, 0, 600, 33, 0)).toBe(0)
    })

    test('returns 0 when count is 1', () => {
      expect(getMiddleRowIndex(0, 33, 33, 600, 33, 1)).toBe(0)
    })

    test('clamps to count - 1', () => {
      const rowHeight = 33
      const count = 10
      const virtualHeight = count * rowHeight // 330
      const placeholderHeight = virtualHeight
      const windowHeight = 600

      // Window is larger than content, so middle would overshoot
      const result = getMiddleRowIndex(
        0,
        placeholderHeight,
        virtualHeight,
        windowHeight,
        rowHeight,
        count
      )
      expect(result).toBeLessThanOrEqual(count - 1)
      expect(result).toBeGreaterThanOrEqual(0)
    })
  })

  describe('virtualToRealScrollTop', () => {
    test('round-trip: virtualToReal(realToVirtual(x)) ≈ x', () => {
      const virtualHeight = 16500000
      const placeholderHeight = MAX_SAFE_SCROLL_HEIGHT
      const windowHeight = 600
      const maxRealScroll = placeholderHeight - windowHeight

      const testValues = [
        0,
        100,
        maxRealScroll / 4,
        maxRealScroll / 2,
        maxRealScroll,
      ]
      for (const x of testValues) {
        const virtual = realToVirtualScrollTop(
          x,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
        const real = virtualToRealScrollTop(
          virtual,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
        expect(real).toBeCloseTo(x, 5)
      }
    })

    test('identity mapping for small tables', () => {
      const virtualHeight = 3300
      const placeholderHeight = 3300
      const windowHeight = 600

      expect(
        virtualToRealScrollTop(
          500,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBeCloseTo(500, 5)
    })

    test('edge case: maxVirtualScroll=0 returns virtualScrollTop directly', () => {
      const virtualHeight = 500
      const placeholderHeight = 500
      const windowHeight = 600

      // maxVirtualScroll = max(500-600, 0) = 0, so returns virtualScrollTop as-is
      expect(
        virtualToRealScrollTop(
          0,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(0)

      expect(
        virtualToRealScrollTop(
          42,
          placeholderHeight,
          virtualHeight,
          windowHeight
        )
      ).toBe(42)
    })
  })

  describe('compensateScrollTop', () => {
    const rowHeight = 33
    const windowHeight = 600

    test('preserves virtual position when count increases', () => {
      const oldCount = 500000
      const newCount = 500100
      const oldVirtualHeight = oldCount * rowHeight
      const oldPlaceholder = Math.min(oldVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const maxRealScroll = oldPlaceholder - windowHeight
      const scrollTop = maxRealScroll / 2

      // Compute the virtual position before and after compensation
      const oldVirtual = realToVirtualScrollTop(
        scrollTop,
        oldPlaceholder,
        oldVirtualHeight,
        windowHeight
      )

      const newScrollTop = compensateScrollTop(
        scrollTop,
        oldCount,
        newCount,
        windowHeight,
        windowHeight,
        rowHeight
      )

      const newVirtualHeight = newCount * rowHeight
      const newPlaceholder = Math.min(newVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const newVirtual = realToVirtualScrollTop(
        newScrollTop,
        newPlaceholder,
        newVirtualHeight,
        windowHeight
      )

      expect(newVirtual).toBeCloseTo(oldVirtual, 2)
    })

    test('preserves virtual position when count decreases', () => {
      const oldCount = 500000
      const newCount = 499900
      const oldVirtualHeight = oldCount * rowHeight
      const oldPlaceholder = Math.min(oldVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const maxRealScroll = oldPlaceholder - windowHeight
      const scrollTop = maxRealScroll * 0.75

      const oldVirtual = realToVirtualScrollTop(
        scrollTop,
        oldPlaceholder,
        oldVirtualHeight,
        windowHeight
      )

      const newScrollTop = compensateScrollTop(
        scrollTop,
        oldCount,
        newCount,
        windowHeight,
        windowHeight,
        rowHeight
      )

      const newVirtualHeight = newCount * rowHeight
      const newPlaceholder = Math.min(newVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const newVirtual = realToVirtualScrollTop(
        newScrollTop,
        newPlaceholder,
        newVirtualHeight,
        windowHeight
      )

      expect(newVirtual).toBeCloseTo(oldVirtual, 2)
    })

    test('preserves virtual position when window height changes', () => {
      const count = 500000
      const oldWindowHeight = 600
      const newWindowHeight = 800
      const oldVirtualHeight = count * rowHeight
      const oldPlaceholder = Math.min(oldVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const maxRealScroll = oldPlaceholder - oldWindowHeight
      const scrollTop = maxRealScroll / 3

      const oldVirtual = realToVirtualScrollTop(
        scrollTop,
        oldPlaceholder,
        oldVirtualHeight,
        oldWindowHeight
      )

      const newScrollTop = compensateScrollTop(
        scrollTop,
        count,
        count,
        oldWindowHeight,
        newWindowHeight,
        rowHeight
      )

      const newPlaceholder = Math.min(oldVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const newVirtual = realToVirtualScrollTop(
        newScrollTop,
        newPlaceholder,
        oldVirtualHeight,
        newWindowHeight
      )

      expect(newVirtual).toBeCloseTo(oldVirtual, 2)
    })

    test('no-op when below MAX_SAFE_SCROLL_HEIGHT', () => {
      const count = 100
      const scrollTop = 500

      const result = compensateScrollTop(
        scrollTop,
        count,
        count + 1,
        windowHeight,
        windowHeight,
        rowHeight
      )

      // Both old and new virtual heights are below the cap, so the
      // mapping is 1:1 and the result equals the input.
      expect(result).toBeCloseTo(scrollTop, 5)
    })

    test('scrollTop=0 stays at 0', () => {
      const result = compensateScrollTop(
        0,
        500000,
        500100,
        windowHeight,
        windowHeight,
        rowHeight
      )
      expect(result).toBe(0)
    })

    test('scrollTop at max maps correctly after count change', () => {
      const oldCount = 500000
      const newCount = 600000
      const oldVirtualHeight = oldCount * rowHeight
      const oldPlaceholder = Math.min(oldVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const maxRealScroll = oldPlaceholder - windowHeight

      const result = compensateScrollTop(
        maxRealScroll,
        oldCount,
        newCount,
        windowHeight,
        windowHeight,
        rowHeight
      )

      // At max scroll with old params, virtual position was at the end.
      // After compensation, it should map back to the same virtual end.
      const newVirtualHeight = newCount * rowHeight
      const newPlaceholder = Math.min(newVirtualHeight, MAX_SAFE_SCROLL_HEIGHT)
      const newMaxRealScroll = newPlaceholder - windowHeight
      // Since both are capped at MAX_SAFE_SCROLL_HEIGHT, maxRealScroll
      // is the same, but the virtual position it maps to should be preserved.
      expect(result).toBeLessThanOrEqual(newMaxRealScroll)
    })
  })
})
