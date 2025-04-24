import { h } from 'vue'
import Handle from '../Handle/Handle.vue'

// Local definition of Position instead of importing it
const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

// Converting to a component with options API instead of a functional component
export default {
  name: 'InputNode',
  props: {
    sourcePosition: {
      type: String,
      default: Position.Bottom,
    },
    label: {
      type: [String, Object],
      default: '',
    },
    connectable: {
      type: Boolean,
      default: false,
    },
    isValidSourcePos: Function,
    data: {
      type: Object,
      default: () => ({}),
    },
    id: String,
  },
  inheritAttrs: false,
  compatConfig: { MODE: 3 },

  render() {
    // Access props via this
    const {
      sourcePosition,
      label: _label,
      connectable,
      isValidSourcePos,
      data,
    } = this

    // Use data.label if available, otherwise use _label
    const label = (data && data.label) || _label || ''

    // In Vue 2, a component must return a single root element
    return h('div', { class: 'vue-flow__node-content' }, [
      typeof label !== 'string' && label
        ? h(label)
        : h('span', { class: 'vue-flow__node-label' }, [label]),
      h(Handle, {
        props: {
          type: 'source',
          position: sourcePosition,
          connectable,
          isValidConnection: isValidSourcePos,
        },
      }),
    ])
  },
}
