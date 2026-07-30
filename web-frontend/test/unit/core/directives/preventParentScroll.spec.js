import preventParentScroll from '@baserow/modules/core/directives/preventParentScroll'

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
    preventParentScroll.beforeMount(child, { value: undefined, modifiers: {} })
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()
  })

  test('does not stop propagation when the binding value is false', () => {
    preventParentScroll.beforeMount(child, { value: false, modifiers: {} })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('whenScrollable lets the event propagate if the element does not overflow', () => {
    preventParentScroll.beforeMount(child, {
      value: undefined,
      modifiers: { whenScrollable: true },
    })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('whenScrollable stops propagation if the element overflows', () => {
    preventParentScroll.beforeMount(child, {
      value: undefined,
      modifiers: { whenScrollable: true },
    })
    makeOverflowing()
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()
  })

  test('whenScrollable reacts to overflow changes after mount', () => {
    preventParentScroll.beforeMount(child, {
      value: undefined,
      modifiers: { whenScrollable: true },
    })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)

    makeOverflowing()
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('whenScrollable respects a false binding value', () => {
    preventParentScroll.beforeMount(child, {
      value: false,
      modifiers: { whenScrollable: true },
    })
    makeOverflowing()
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('updated hook can enable whenScrollable from a disabled state', () => {
    preventParentScroll.beforeMount(child, {
      value: false,
      modifiers: { whenScrollable: true },
    })
    preventParentScroll.updated(child, {
      value: true,
      oldValue: false,
      modifiers: { whenScrollable: true },
    })
    makeOverflowing()
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()
  })

  test('updated hook can disable the directive', () => {
    preventParentScroll.beforeMount(child, { value: true, modifiers: {} })
    dispatchWheel()
    expect(parentListener).not.toHaveBeenCalled()

    preventParentScroll.updated(child, {
      value: false,
      oldValue: true,
      modifiers: {},
    })
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })

  test('unmounted removes the listeners', () => {
    preventParentScroll.beforeMount(child, { value: true, modifiers: {} })
    preventParentScroll.unmounted(child)
    dispatchWheel()
    expect(parentListener).toHaveBeenCalledTimes(1)
  })
})
