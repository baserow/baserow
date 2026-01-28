/**
 * Allow to wrap a component with a list of components + props. This is a render
 * function instead of a template to avoid extra div and improve performances.
 */
import { h } from 'vue'

export default {
  name: 'RecursiveWrapper',
  props: {
    components: {
      type: Array,
      required: true,
    },
    firstComponentClass: { type: String, required: false, default: null },
  },
  render() {
    const rec = ([first, ...rest], firstComponentClass = null) => {
      if (first) {
        const props = { ...(first.props || {}) }
        if (firstComponentClass) props.class = firstComponentClass

        return h(first.component, props, {
          default: () => rec(rest),
        })
      }

      return this.$slots.default ? this.$slots.default() : []
    }

    return rec(this.components, this.firstComponentClass)
  },
}
