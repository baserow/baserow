<template>
  <span class="invitation-link-target-field" :title="row.targetName">
    {{ row.targetName }}
  </span>
</template>

<script setup>
defineProps({
  row: { type: Object, required: true },
  column: { type: Object, required: true },
})
</script>
