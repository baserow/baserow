import { expect, test, vi } from 'vitest'
import sortable from '@baserow/modules/core/directives/sortable'

test.each(['visible', 'inert', 'hidden'])(
  'waits for a drag and only reorders a list that is still visible (%s)',
  (listState) => {
    const list = document.createElement('ul')
    const first = document.createElement('li')
    const second = document.createElement('li')
    list.append(first, second)
    document.body.append(list)
    first.style.visibility = 'visible'
    vi.spyOn(first, 'getClientRects').mockImplementation(() =>
      list.style.display === 'none' ? [] : [new DOMRect(0, 0, 10, 10)]
    )

    const update = vi.fn()
    const firstBinding = { dir: sortable, value: { id: 1, update } }
    const secondBinding = { dir: sortable, value: { id: 2, update } }
    sortable.beforeMount(first, firstBinding)
    sortable.beforeMount(second, secondBinding)

    const sendMouseEvent = (target, type, clientY) => {
      target.dispatchEvent(
        new MouseEvent(type, { clientY, bubbles: true, cancelable: true })
      )
    }

    try {
      sendMouseEvent(first, 'mousedown', 10)
      expect(list.firstElementChild).toBe(first)
      sendMouseEvent(window, 'mousemove', 12)
      expect(list.firstElementChild).toBe(first)
      sendMouseEvent(window, 'mouseup', 12)
      expect(update).not.toHaveBeenCalled()

      sendMouseEvent(first, 'mousedown', 10)
      sendMouseEvent(window, 'mousemove', 15)
      expect(list.firstElementChild.className).toBe(
        'sortable-position-indicator'
      )
      if (listState === 'inert') {
        list.setAttribute('inert', '')
      } else if (listState === 'hidden') {
        list.style.display = 'none'
      }
      sendMouseEvent(window, 'mouseup', 15)
      expect(list.firstElementChild).toBe(first)
      if (listState === 'visible') {
        expect(update).toHaveBeenCalledWith([2, 1], [1, 2], 1, null)
      } else {
        expect(update).not.toHaveBeenCalled()
      }
    } finally {
      sortable.cancel(first)
      sortable.unmounted(first, firstBinding)
      sortable.unmounted(second, secondBinding)
      list.remove()
      vi.restoreAllMocks()
    }
  }
)
