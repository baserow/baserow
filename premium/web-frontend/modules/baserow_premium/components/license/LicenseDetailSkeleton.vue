<template>
  <div class="skeleton license-detail" aria-hidden="true">
    <SkeletonBlock width="260px" height="28px"></SkeletonBlock>
    <div class="license-detail__users">
      <SkeletonBlock
        width="120px"
        height="24px"
        class="margin-top-3 margin-bottom-2"
      ></SkeletonBlock>
      <SkeletonBlock width="400px" height="12px"></SkeletonBlock>
      <SkeletonBlock
        width="380px"
        height="12px"
        class="margin-top-1"
      ></SkeletonBlock>
      <SkeletonBlock
        width="260px"
        height="12px"
        class="margin-top-1"
      ></SkeletonBlock>
      <SkeletonBlock
        width="400px"
        height="16px"
        class="margin-top-3"
      ></SkeletonBlock>
    </div>
    <div class="license-detail__body">
      <div class="license-detail__body-left">
        <div
          v-for="index in count"
          :key="`item-${index}`"
          class="license-detail__item"
        >
          <div class="license-detail__item-label">
            <div class="license-detail__item-name">
              <SkeletonBlock width="140px"></SkeletonBlock>
            </div>
          </div>
          <div class="license-detail__item-value">
            <SkeletonBlock width="180px"></SkeletonBlock>
          </div>
        </div>
      </div>
      <div class="license-detail__body-right">
        <SkeletonBlock height="280px"></SkeletonBlock>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * The license detail page while the license is fetched. It mirrors the rows of
 * the detail list, so that the page keeps its shape once it arrives.
 */
export default {
  name: 'LicenseDetailSkeleton',
  props: {
    count: {
      required: false,
      type: Number,
      default: 10,
    },
  },
}
</script>
