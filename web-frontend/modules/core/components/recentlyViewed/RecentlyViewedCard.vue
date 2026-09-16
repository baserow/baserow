<template>
  <ItemCard
    :name="item.name"
    :icon="item.iconClass"
    :icon-color="item.iconColor"
    :loading="item.loading"
    :title="item.parentPath.join(' › ')"
    @click="$emit('click')"
  >
    <template #meta>
      {{ item.typeName }}
      <span class="item-card__meta-separator">&#8226;</span>
      {{ $t('common.viewedAgo', { ago: item.lastViewedLabel }) }}
    </template>
  </ItemCard>
</template>

<script setup>
import ItemCard from '@baserow/modules/core/components/ItemCard'

defineProps({
  // A presented entry, see `presentEntry` in `RecentlyViewed.vue`.
  item: {
    type: Object,
    required: true,
  },
})

defineEmits(['click'])
</script>
