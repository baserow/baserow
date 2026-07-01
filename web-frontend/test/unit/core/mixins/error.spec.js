import error from '@baserow/modules/core/mixins/error'

describe('error mixin focusOnError', () => {
  const { focusOnError } = error.methods

  test('scrolls to the error element when $el is a real element', () => {
    const scrollIntoView = vi.fn()
    const errorElement = { scrollIntoView }
    const $el = {
      querySelector: vi.fn(() => errorElement),
    }

    focusOnError.call({ $el })

    expect($el.querySelector).toHaveBeenCalledWith('[data-error]')
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' })
  })

  test('does not throw when $el is a fragment placeholder without querySelector', () => {
    // In Vue 3 a component with a root-level v-if (like the Error component)
    // is a fragment, so $el is a comment placeholder node that has no
    // querySelector. The mixin should fall back to the parent element.
    const scrollIntoView = vi.fn()
    const errorElement = { scrollIntoView }
    const parentElement = {
      querySelector: vi.fn(() => errorElement),
    }
    // A comment/text placeholder node: no querySelector method.
    const $el = { parentElement }

    expect(() => focusOnError.call({ $el })).not.toThrow()
    expect(parentElement.querySelector).toHaveBeenCalledWith('[data-error]')
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' })
  })

  test('does nothing when no error element is found', () => {
    const $el = { querySelector: vi.fn(() => null) }
    expect(() => focusOnError.call({ $el })).not.toThrow()
  })

  test('does not throw when $el is a placeholder with no parent element', () => {
    const $el = { parentElement: null }
    expect(() => focusOnError.call({ $el })).not.toThrow()
  })
})
