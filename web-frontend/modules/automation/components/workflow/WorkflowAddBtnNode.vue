<template>
  <ButtonFloating
    icon="iconoir-plus"
    size="small"
    @click="emit('addNode', props.data.nodeId)"
  ></ButtonFloating>
</template>

<script setup>
const props = defineProps({
  id: {
    type: String,
    default: null,
  },
  position: {
    type: Object,
    default: () => ({ x: 0, y: 0 }),
  },
  data: {
    type: Object,
    default: () => ({ nodeId: null }),
  },
})

const emit = defineEmits(['addNode'])
</script>
