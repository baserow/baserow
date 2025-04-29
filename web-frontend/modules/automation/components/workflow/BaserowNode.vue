<template>
  <div class="baserow-node">{{ label }} ID: {{ id }}</div>
</template>

<script setup>
defineProps({
  id: {
    type: String,
    default: null,
  },
  label: {
    type: String,
    default: null,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  dragging: {
    type: Boolean,
    default: false,
  },
})
</script>
