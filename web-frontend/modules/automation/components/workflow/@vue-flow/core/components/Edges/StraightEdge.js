import { h } from 'vue'
import BaseEdge from './BaseEdge.vue'
import { getStraightPath } from './utils'

// Converting to a component with options API instead of a functional component
export default {
  name: 'StraightEdge',
  props: {
    label: [String, Object],
    labelStyle: Object,
    labelShowBg: Boolean,
    labelBgStyle: Object,
    labelBgPadding: [Number, Array],
    labelBgBorderRadius: Number,
    sourceY: Number,
    sourceX: Number,
    targetX: Number,
    targetY: Number,
    markerEnd: String,
    markerStart: String,
    interactionWidth: Number,
  },
  compatConfig: { MODE: 3 },
  inheritAttrs: false,

  render() {
    const [path, labelX, labelY] = getStraightPath(this.$props)

    return h(BaseEdge, {
      props: {
        path,
        labelX,
        labelY,
        ...this.$props,
      },
      attrs: this.$attrs,
    })
  },
}
