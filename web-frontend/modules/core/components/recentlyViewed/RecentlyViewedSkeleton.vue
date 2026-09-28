<template>
  <div class="skeleton" aria-hidden="true">
    <div v-if="viewMode !== 'cards'" class="recently-viewed__table">
      <RecentlyViewedHead :show-workspace="showWorkspace"></RecentlyViewedHead>
      <div
        v-for="index in count"
        :key="`skeleton-row-${index}`"
        class="recently-viewed__row recently-viewed__row--skeleton"
        :class="{ 'recently-viewed__row--with-workspace': showWorkspace }"
      >
        <div class="recently-viewed__cell">
          <SkeletonBlock
            width="40px"
            height="40px"
            shape="square"
          ></SkeletonBlock>
          <div
            class="recently-viewed__name-details recently-viewed__name-details--skeleton"
          >
            <SkeletonBlock width="140px"></SkeletonBlock>
            <SkeletonBlock width="220px" height="10px"></SkeletonBlock>
          </div>
        </div>
        <div class="recently-viewed__cell">
          <SkeletonBlock width="80px"></SkeletonBlock>
        </div>
        <div v-if="showWorkspace" class="recently-viewed__cell">
          <SkeletonBlock
            width="24px"
            height="24px"
            shape="square"
          ></SkeletonBlock>
          <SkeletonBlock width="100px"></SkeletonBlock>
        </div>
      </div>
    </div>
    <div v-else class="recently-viewed__grid">
      <div
        v-for="index in count"
        :key="`skeleton-card-${index}`"
        class="item-card item-card--skeleton"
      >
        <SkeletonBlock
          width="40px"
          height="40px"
          shape="square"
        ></SkeletonBlock>
        <div class="item-card__details item-card__details--skeleton">
          <SkeletonBlock width="140px"></SkeletonBlock>
          <SkeletonBlock width="180px" height="10px"></SkeletonBlock>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import RecentlyViewedHead from '@baserow/modules/core/components/recentlyViewed/RecentlyViewedHead'

/**
 * The recently viewed list while its items are being fetched. It renders the
 * real row and card structure, so nothing resizes once the items arrive.
 */
defineProps({
  viewMode: {
    type: String,
    required: true,
  },
  showWorkspace: {
    type: Boolean,
    required: false,
    default: false,
  },
  count: {
    type: Number,
    required: false,
    default: 5,
  },
})
</script>
