/**
 * Allow to wrap a component with a list of components + props. This is a render
 * function instead of a template to avoid extra div and improve performances.
 */
export default {
  name: 'RecursiveWrapper',
  functional: true,
  props: {
    components: {
      type: Array,
      required: true,
    },
    firstComponentClass: { type: String, required: false, default: null },
  },
  render(h, context) {
    const rec = ([first, ...rest], firstComponentClass = null) => {
      if (first) {
        return h(
          first.component,
          { props: first.props, class: firstComponentClass },
          rec(rest)
        )
      } else {
        return context.slots().default
      }
    }

    return rec(context.props.components, context.props.firstComponentClass)
  },
}
