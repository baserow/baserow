import preventParentScroll, {
  WHEN_SCROLLABLE,
} from '@baserow/modules/core/directives/preventParentScroll'

describe('preventParentScroll directive', () => {
  let parent
  let child
  let parentListener

  beforeEach(() => {
    parent = document.createElement('div')
    child = document.createElement('div')
    parent.appendChild(child)
    parentListener = vi.fn()
    parent.addEventListener('wheel', parentListener)
  })

  const dispatchWheel = () => {
    child.dispatchEvent(new Event('wheel', { bubbles: true }))
  }

  const makeOverflowing = () => {
    Object.defineProperties(child, {
      scrollHeight: { value: 200, configurable: true },
      clientHeight: { value: 100, configurable: true },
    })
  }

  test('stops propagation to the parent by default', () => {
    preventParentScroll.beforeMount(child, { value: undefined })
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()
  })

  test('does not stop propagation when the binding value is false', () => {
    preventParentScroll.beforeMount(child, { value: false })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('when-scrollable lets the event propagate if the element does not overflow', () => {
    preventParentScroll.beforeMount(child, { value: WHEN_SCROLLABLE })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('when-scrollable stops propagation if the element overflows', () => {
    preventParentScroll.beforeMount(child, { value: WHEN_SCROLLABLE })
    makeOverflowing()
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()
  })

  test('when-scrollable reacts to overflow changes after mount', () => {
    preventParentScroll.beforeMount(child, { value: WHEN_SCROLLABLE })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)

    makeOverflowing()
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('updated hook switches between modes', () => {
    preventParentScroll.beforeMount(child, { value: true })
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()

    preventParentScroll.updated(child, {
      value: WHEN_SCROLLABLE,
      oldValue: true,
    })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('updated hook can enable when-scrollable from a disabled state', () => {
    preventParentScroll.beforeMount(child, { value: false })
    preventParentScroll.updated(child, {
      value: WHEN_SCROLLABLE,
      oldValue: false,
    })
    makeOverflowing()
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()
  })

  test('unmounted removes the listeners', () => {
    preventParentScroll.beforeMount(child, { value: true })
    preventParentScroll.unmounted(child)
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })
})
