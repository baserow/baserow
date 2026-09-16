<template>
  <div class="recently-viewed__table">
    <RecentlyViewedHead :show-workspace="showWorkspace"></RecentlyViewedHead>
    <RecentlyViewedRow
      v-for="item in items"
      :key="item.key"
      :item="item"
      :show-workspace="showWorkspace"
      @click="$emit('open', item)"
    ></RecentlyViewedRow>
  </div>
</template>

<script setup>
import RecentlyViewedHead from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedHead'
import RecentlyViewedRow from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedRow'

defineProps({
  items: {
    type: Array,
    required: true,
  },
  showWorkspace: {
    type: Boolean,
    required: false,
    default: false,
  },
})

defineEmits(['open'])
</script>
