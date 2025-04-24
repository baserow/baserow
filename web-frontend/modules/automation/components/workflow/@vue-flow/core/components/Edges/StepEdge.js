import { h } from 'vue'
import SmoothStepEdge from './SmoothStepEdge'

// Converting to a component with options API instead of a functional component
export default {
  name: 'StepEdge',
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
    markerEnd: String,
    markerStart: String,
    interactionWidth: Number,
  },
  compatConfig: { MODE: 3 },
  inheritAttrs: false,

  render() {
    return h(SmoothStepEdge, {
      props: {
        ...this.$props,
        borderRadius: 0,
      },
      attrs: this.$attrs,
    })
  },
}
