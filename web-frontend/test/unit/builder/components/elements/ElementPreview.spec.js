import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview'

describe('ElementPreview', () => {
  let originalIntersectionObserver = null
  let observerOptions = null

  beforeEach(() => {
    observerOptions = null
    originalIntersectionObserver = globalThis.IntersectionObserver
    globalThis.IntersectionObserver = class {
      constructor(callback, options) {
        // Same validation as the browsers for the top margin.
        if (!/^\d+(\.\d+)?px /.test(options.rootMargin.replace(/^-/, ''))) {
          throw new SyntaxError(
            "Failed to construct 'IntersectionObserver': rootMargin must be " +
              'specified in absolute length units or percent.'
          )
        }
        observerOptions = options
      }

      disconnect = vi.fn()
      observe = vi.fn()
    }
  })

  afterEach(() => {
    globalThis.IntersectionObserver = originalIntersectionObserver
  })

  const setupIntersectionObserver = (pageTop) => {
    const component = {
      pageTop,
      observer: null,
      $el: {},
      $nextTick: (callback) => callback(),
    }
    ElementPreview.methods.setupIntersectionObserver.call(component)
    return component
  }

  test.each([
    [120, '-120px 0px 0px 0px'],
    [12.5, '-12.5px 0px 0px 0px'],
    [-40, '-0px 0px 0px 0px'],
    [Infinity, '-0px 0px 0px 0px'],
    [NaN, '-0px 0px 0px 0px'],
    [undefined, '-0px 0px 0px 0px'],
  ])('uses a valid root margin when the page top is %s', (pageTop, margin) => {
    const component = setupIntersectionObserver(pageTop)

    expect(observerOptions.rootMargin).toBe(margin)
    expect(component.observer.observe).toHaveBeenCalledWith(component.$el)
  })
})
