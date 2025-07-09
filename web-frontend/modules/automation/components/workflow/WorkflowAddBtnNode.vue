<template>
  <ButtonFloating
    icon="iconoir-plus"
    size="small"
    :disabled="props.data.disabled"
    title="Create automation node"
    @click="handleClick"
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

const handleClick = () => {
  if (!props.data.disabled) {
    emit('addNode', props.data.nodeId)
  }
}
</script>
