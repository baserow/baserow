import sortable from '@baserow/modules/core/directives/sortable'

describe('sortable directive', () => {
  let parent, items, bindings, update

  const rectangle = (left, top, width = 100, height = 40) => ({
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
  })

  const mountItems = (rects, options = {}) => {
    update = vi.fn()
    parent = document.createElement('div')
    parent.getBoundingClientRect = () => rectangle(100, 50, 340, 160)
    document.body.appendChild(parent)
    bindings = []
    items = rects.map((rect, index) => {
      const item = document.createElement('div')
      item.getBoundingClientRect = () => rect
      item.innerHTML = '<button data-handle>Move</button><input />'
      parent.appendChild(item)
      const binding = {
        value: { id: index + 1, update, handle: '[data-handle]', ...options },
        dir: sortable,
      }
      bindings.push(binding)
      sortable.beforeMount(item, binding)
      return item
    })
  }

  const mouse = (target, type, clientX, clientY) => {
    target.dispatchEvent(
      new MouseEvent(type, {
        bubbles: true,
        cancelable: true,
        button: 0,
        clientX,
        clientY,
      })
    )
  }

  const drag = (index, x, y) => {
    const { left, top } = items[index].getBoundingClientRect()
    mouse(items[index].querySelector('[data-handle]'), 'mousedown', left, top)
    mouse(window, 'mousemove', x, y)
  }

  afterEach(() => {
    mouse(window, 'mouseup', 0, 0)
    items.forEach((item, index) => sortable.unmounted(item, bindings[index]))
    parent.remove()
  })

  describe('horizontal rows', () => {
    beforeEach(() => {
      mountItems(
        [
          rectangle(100, 50),
          rectangle(220, 50),
          rectangle(340, 50),
          rectangle(100, 110),
        ],
        { direction: 'horizontal' }
      )
    })

    test('moves right within a row and shows the insertion line in the gap', () => {
      drag(0, 330, 70)

      const indicator = parent.querySelector('.sortable-position-indicator')
      expect(indicator.style.left).toBe('228.5px')
      expect(indicator.style.top).toBe('0px')
      expect(indicator.style.width).toBe('3px')
      expect(indicator.style.height).toBe('40px')

      mouse(window, 'mouseup', 330, 70)

      expect(update).toHaveBeenCalledWith([2, 1, 3, 4], [1, 2, 3, 4], 1, 3)
      expect(parent.querySelector('.sortable-position-indicator')).toBeNull()
    })

    test('moves left within a row', () => {
      drag(2, 110, 70)
      mouse(window, 'mouseup', 110, 70)

      expect(update).toHaveBeenCalledWith([3, 1, 2, 4], [1, 2, 3, 4], 3, 1)
    })

    test('shows the end of the current row when inserting before a wrapped row', () => {
      drag(0, 470, 70)

      const indicator = parent.querySelector('.sortable-position-indicator')
      expect(indicator.style.left).toBe('338.5px')
      expect(indicator.style.top).toBe('0px')

      mouse(window, 'mouseup', 470, 70)
      expect(update).toHaveBeenCalledWith([2, 3, 1, 4], [1, 2, 3, 4], 1, 4)
    })

    test('moves into the beginning of a wrapped row', () => {
      drag(0, 110, 130)

      const indicator = parent.querySelector('.sortable-position-indicator')
      expect(indicator.style.left).toBe('-1.5px')
      expect(indicator.style.top).toBe('60px')

      mouse(window, 'mouseup', 110, 130)
      expect(update).toHaveBeenCalledWith([2, 3, 1, 4], [1, 2, 3, 4], 1, 4)
    })

    test('moves to the end of the last row', () => {
      drag(0, 210, 130)

      const indicator = parent.querySelector('.sortable-position-indicator')
      expect(indicator.style.left).toBe('98.5px')
      expect(indicator.style.top).toBe('60px')

      mouse(window, 'mouseup', 210, 130)
      expect(update).toHaveBeenCalledWith([2, 3, 4, 1], [1, 2, 3, 4], 1, null)
    })

    test('Escape cancels a move without changing the order', () => {
      drag(0, 330, 70)
      document.body.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
      )
      mouse(window, 'mouseup', 330, 70)

      expect(update).not.toHaveBeenCalled()
      expect(parent.querySelector('.sortable-position-indicator')).toBeNull()
      expect(parent.querySelector('.sortable-sorting-item')).toBeNull()
    })

    test('dropping at the original position does not save an order', () => {
      drag(0, 170, 70)
      mouse(window, 'mouseup', 170, 70)

      expect(update).not.toHaveBeenCalled()
    })

    test('input interactions do not start dragging', () => {
      mouse(items[0].querySelector('input'), 'mousedown', 110, 70)
      mouse(window, 'mousemove', 330, 70)
      mouse(window, 'mouseup', 330, 70)

      expect(update).not.toHaveBeenCalled()
      expect(parent.querySelector('.sortable-position-indicator')).toBeNull()
    })

    test('an updated disabled binding prevents dragging', () => {
      sortable.updated(items[0], {
        ...bindings[0],
        value: { ...bindings[0].value, enabled: false },
      })
      drag(0, 330, 70)
      mouse(window, 'mouseup', 330, 70)

      expect(update).not.toHaveBeenCalled()
      expect(parent.querySelector('.sortable-position-indicator')).toBeNull()
    })
  })

  test('keeps the default vertical ordering and horizontal insertion line', () => {
    mountItems([rectangle(100, 50), rectangle(100, 110), rectangle(100, 170)])
    drag(0, 110, 150)

    const indicator = parent.querySelector('.sortable-position-indicator')
    expect(indicator.style.width).toBe('100px')
    expect(indicator.style.height).toBe('')
    expect(indicator.style.top).toBe('120px')

    mouse(window, 'mouseup', 110, 150)
    expect(update).toHaveBeenCalledWith([2, 1, 3], [1, 2, 3], 1, 3)
  })

  test('keeps differently sized items on the same horizontal row', () => {
    mountItems(
      [
        rectangle(100, 60, 100, 30),
        rectangle(220, 50),
        rectangle(340, 60, 100, 30),
        rectangle(100, 110),
      ],
      { direction: 'horizontal' }
    )
    drag(0, 330, 70)

    const indicator = parent.querySelector('.sortable-position-indicator')
    expect(indicator.style.top).toBe('0px')
    expect(indicator.style.height).toBe('40px')

    mouse(window, 'mouseup', 330, 70)
    expect(update).toHaveBeenCalledWith([2, 1, 3, 4], [1, 2, 3, 4], 1, 3)
  })
})
