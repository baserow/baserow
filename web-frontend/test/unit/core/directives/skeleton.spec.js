import skeleton from '@baserow/modules/core/directives/skeleton'

describe('skeleton', () => {
  test('marks the element as loading and cleans up when the data arrives', () => {
    const element = document.createElement('div')

    skeleton.mounted(element, { value: { loading: true, width: '64px' } })

    expect(element.classList.contains('skeleton-loading')).toBe(true)
    expect(element.getAttribute('aria-busy')).toBe('true')
    expect(element.style.getPropertyValue('--skeleton-width')).toBe('64px')

    skeleton.updated(element, { value: { loading: false, width: '64px' } })

    expect(element.classList.contains('skeleton-loading')).toBe(false)
    expect(element.getAttribute('class')).toBe(null)
    expect(element.getAttribute('aria-busy')).toBe(null)
    expect(element.style.getPropertyValue('--skeleton-width')).toBe('')
  })

  test('accepts a boolean and only applies known shapes', () => {
    const element = document.createElement('div')

    skeleton.mounted(element, { value: true })

    expect(element.classList.contains('skeleton-loading')).toBe(true)
    expect(element.className).not.toContain('skeleton-loading--')

    skeleton.updated(element, { value: { loading: true, shape: 'circle' } })

    expect(element.classList.contains('skeleton-loading--circle')).toBe(true)

    skeleton.updated(element, { value: { loading: true, shape: 'unknown' } })

    expect(element.classList.contains('skeleton-loading--circle')).toBe(false)
  })

  test('renders the placeholder server side', () => {
    expect(
      skeleton.getSSRProps({ value: { loading: true, height: '100%' } })
    ).toMatchObject({
      class: ['skeleton-loading', null],
      style: '--skeleton-height: 100%',
      'aria-busy': 'true',
    })
    expect(skeleton.getSSRProps({ value: false })).toEqual({})
  })
})
