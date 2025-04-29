// Version LinePattern pour Vue 2.7
export const LinePattern = {
  functional: true,
  props: {
    dimensions: { type: Array, required: true },
    size: { type: Number, default: 1 },
    color: { type: String, required: true },
  },
  render(h, ctx) {
    const { dimensions, size, color } = ctx.props
    console.log('LinePattern rendering with:', { dimensions, size, color })

    return h('path', {
      attrs: {
        stroke: color,
        'stroke-width': size,
        d: `M${dimensions[0] / 2} 0 V${dimensions[1]} M0 ${
          dimensions[1] / 2
        } H${dimensions[0]}`,
      },
    })
  },
}

// Version DotPattern pour Vue 2.7
export const DotPattern = {
  functional: true,
  props: {
    radius: { type: Number, default: 5 },
    color: { type: String, default: 'red' },
  },
  render(h, ctx) {
    const { radius, color } = ctx.props
    console.log('DotPattern rendering with:', { radius, color })

    return h('circle', {
      attrs: {
        cx: radius,
        cy: radius,
        r: radius,
        fill: color,
      },
    })
  },
}

// Export des patterns pour Vue 2.7
export const Patterns = {
  lines: LinePattern,
  dots: DotPattern,
}

export const DefaultBgColors = {
  dots: '#81818a',
  lines: '#eee',
}
