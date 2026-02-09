<template>
  <a class="element-preview__insert" @click="$emit('click')">
    <i class="baserow-icon-plus"></i>
  </a>
</template>

<script>
export default {
  name: 'InsertElementButton',
  emits: ['click'],
}
</script>
