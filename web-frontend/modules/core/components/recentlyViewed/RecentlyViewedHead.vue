<template>
  <div
    class="recently-viewed__head"
    :class="{ 'recently-viewed__head--with-workspace': showWorkspace }"
  >
    <div class="recently-viewed__head-cell">
      {{ $t('recentlyViewed.name') }}
    </div>
    <div class="recently-viewed__head-cell">
      {{ $t('recentlyViewed.lastViewed') }}
    </div>
    <div v-if="showWorkspace" class="recently-viewed__head-cell">
      {{ $t('recentlyViewed.workspace') }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  showWorkspace: {
    type: Boolean,
    required: false,
    default: false,
  },
})
</script>
