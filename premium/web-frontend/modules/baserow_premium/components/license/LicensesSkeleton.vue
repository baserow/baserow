<template>
  <div class="skeleton licenses" aria-hidden="true">
    <div class="licenses__head">
      <SkeletonBlock width="140px" height="28px"></SkeletonBlock>
      <SkeletonBlock width="280px" height="36px"></SkeletonBlock>
    </div>
    <div class="margin-bottom-3">
      <SkeletonBlock width="360px"></SkeletonBlock>
    </div>
    <div class="licenses__items">
      <div
        v-for="index in count"
        :key="`license-${index}`"
        class="licenses__item"
      >
        <div class="licenses__item-head">
          <div class="licenses__item-title">
            <SkeletonBlock width="200px" height="18px"></SkeletonBlock>
          </div>
          <SkeletonBlock width="70px" height="18px"></SkeletonBlock>
        </div>
        <div class="licenses__item-validity">
          <SkeletonBlock width="240px"></SkeletonBlock>
        </div>
        <ul class="licenses__item-details">
          <li class="licenses__item-detail-item">
            <SkeletonBlock width="90px" height="10px"></SkeletonBlock>
          </li>
          <li class="licenses__item-detail-item">
            <SkeletonBlock width="120px" height="10px"></SkeletonBlock>
          </li>
        </ul>
        <ul class="licenses__item-details">
          <li
            v-for="feature in featureCount"
            :key="`feature-${feature}`"
            class="licenses__item-detail-item"
          >
            <SkeletonBlock width="80px" height="10px"></SkeletonBlock>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * The licenses overview while the licenses are fetched. It mirrors the cards of
 * the list, so that the page keeps its shape once they arrive.
 */
export default {
  name: 'LicensesSkeleton',
  props: {
    count: {
      required: false,
      type: Number,
      default: 2,
    },
    featureCount: {
      required: false,
      type: Number,
      default: 4,
    },
  },
}
</script>
