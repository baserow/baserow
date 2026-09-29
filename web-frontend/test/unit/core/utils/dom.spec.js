import { onClickOutside } from '@baserow/modules/core/utils/dom'

describe('onClickOutside', () => {
  test('detects an outside click when mousedown propagation is stopped', () => {
    const context = document.createElement('div')
    const outside = document.createElement('div')
    const callback = vi.fn()

    outside.addEventListener('mousedown', (event) => event.stopPropagation())
    document.body.append(context, outside)

    const cancel = onClickOutside(context, callback)

    context.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    context.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    outside.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    outside.dispatchEvent(new MouseEvent('click', { bubbles: true }))

    expect(callback).toHaveBeenCalledOnce()

    cancel()
    context.remove()
    outside.remove()
  })
})
