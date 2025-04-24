<template>
  <div class="baserow-node">{{ nodeLabel }}</div>
</template>

<script>
import { onMounted, computed } from 'vue'

export default {
  props: {
    label: {
      type: String,
      default: null,
    },
    data: {
      type: Object,
      default: null,
    },
  },
  setup(props) {
    // Support both formats: {label: 'text'} and {data: {label: 'text'}}
    const nodeLabel = computed(() => {
      return props.label || (props.data && props.data.label) || 'No Label'
    })

    onMounted(() => {
      console.log('Node label:', nodeLabel.value)
    })

    return {
      nodeLabel,
    }
  },
}
</script>
