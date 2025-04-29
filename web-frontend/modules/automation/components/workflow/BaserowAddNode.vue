<template>
  <ButtonFloating
    icon="iconoir-plus"
    size="small"
    @click="emit('addNode', props.id)"
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
})

const emit = defineEmits(['addNode'])
</script>
