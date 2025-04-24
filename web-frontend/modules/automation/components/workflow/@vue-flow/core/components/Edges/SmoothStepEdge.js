import { h } from 'vue'
import BaseEdge from './BaseEdge.vue'
import { getSmoothStepPath } from './utils'

// Local definition of Position instead of importing it
const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

// Converting to a component with options API instead of a functional component
export default {
  name: 'SmoothStepEdge',
  props: {
    sourcePosition: String,
    targetPosition: String,
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
    borderRadius: Number,
    markerEnd: String,
    markerStart: String,
    interactionWidth: Number,
    offset: Number,
  },
  compatConfig: { MODE: 3 },
  inheritAttrs: false,

  render() {
    const [path, labelX, labelY] = getSmoothStepPath({
      ...this.$props,
      sourcePosition: this.sourcePosition ?? Position.Bottom,
      targetPosition: this.targetPosition ?? Position.Top,
    })

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
