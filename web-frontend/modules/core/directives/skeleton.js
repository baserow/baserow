const SHAPES = ['rounded', 'square', 'circle']

const parseValue = (value) =>
  value !== null && typeof value === 'object' ? value : { loading: value }

const properties = (binding) => {
  const { loading, width, height, shape } = parseValue(binding.value)
  return {
    loading: loading === undefined ? true : !!loading,
    width,
    height,
    shape: SHAPES.includes(shape) ? shape : null,
  }
}

const apply = (el, binding) => {
  const { loading, width, height, shape } = properties(binding)

  el.classList.toggle('skeleton-loading', loading)
  SHAPES.forEach((value) =>
    el.classList.toggle(
      `skeleton-loading--${value}`,
      loading && shape === value
    )
  )

  if (loading) {
    el.setAttribute('aria-busy', 'true')
  } else {
    el.removeAttribute('aria-busy')
  }

  const variable = (name, value) => {
    if (loading && value) {
      el.style.setProperty(name, value)
    } else {
      el.style.removeProperty(name)
    }
  }
  variable('--skeleton-width', width)
  variable('--skeleton-height', height)

  // Only needed while hydrating the server rendered markup, which has happened
  // by the time this runs.
  el.removeAttribute('data-allow-mismatch')
}

/**
 * Replaces the content of the element with a pulsing placeholder while the value
 * is truthy. The content stays in the DOM, but is hidden, so the element keeps
 * the size it has when the data has arrived and nothing shifts once it does.
 *
 * The placeholder is sized after the typography of the element, so it matches
 * whatever it covers without needing page specific styles. Optionally an object
 * can be provided to override the size and shape, which is typically needed when
 * the loaded content is wider than the value that's rendered while loading.
 *
 * ```
 * <div v-skeleton="loading">{{ name }}</div>
 * <div v-skeleton="{ loading, width: '64px' }">{{ total }}</div>
 * <div v-skeleton="{ loading, height: '100%' }"><Chart /></div>
 * ```
 *
 * Note that the element becomes the positioning context of the placeholder, so
 * it can't be used on an absolutely positioned element.
 */
export default {
  mounted: apply,
  updated: apply,
  /**
   * Without this, the server rendered markup would briefly show the empty
   * placeholder data before the client applies the directive. Because a
   * directive can't add the same class while hydrating, the mismatch between
   * both is explicitly allowed.
   */
  getSSRProps(binding) {
    const { loading, width, height, shape } = properties(binding)

    if (!loading) {
      return {}
    }

    const style = []
    if (width) {
      style.push(`--skeleton-width: ${width}`)
    }
    if (height) {
      style.push(`--skeleton-height: ${height}`)
    }

    return {
      class: ['skeleton-loading', shape && `skeleton-loading--${shape}`],
      style: style.join('; ') || undefined,
      'aria-busy': 'true',
      'data-allow-mismatch': 'class,style,attribute',
    }
  },
}
