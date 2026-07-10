<template>
  <button
    v-if="expandable"
    type="button"
    class="data-sync-runs__head data-sync-runs__head--expandable"
    :aria-expanded="expanded"
    :aria-controls="controls"
    @click="$emit('toggle')"
  >
    <slot></slot>
  </button>
  <div v-else class="data-sync-runs__head">
    <slot></slot>
  </div>
</template>

<script>
export default {
  name: 'DataSyncRunHead',
  props: {
    expandable: {
      type: Boolean,
      required: true,
    },
    expanded: {
      type: Boolean,
      required: true,
    },
    controls: {
      type: String,
      required: true,
    },
  },
  emits: ['toggle'],
}
</script>
