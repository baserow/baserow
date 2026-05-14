<template>
  <div
    class="grid-grouped-placeholder"
    :style="{ top: item.y + 'px', height: item.height + 'px' }"
    :data-placeholder-index="item.indexInSection"
  >
    <div class="grid-grouped-placeholder__shimmer" />
  </div>
</template>

<script>
/**
 * Placeholder slot rendered when the section says rowCount = N but the
 * cache only has K < N rows for that section. Shows a subdued shimmer
 * so the user sees the section's eventual size without a layout pop
 * when the missing rows arrive. The container is responsible for
 * scheduling a fetch when a placeholder enters the viewport.
 */
export default {
  name: 'GridGroupedPlaceholder',
  props: {
    item: {
      type: Object,
      required: true,
      validator: (it) => it.type === 'placeholder',
    },
  },
}
</script>

<style lang="scss" scoped>
.grid-grouped-placeholder {
  position: absolute;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  background: #ffffff;
  border-bottom: 1px solid #f0f0f0;
}

.grid-grouped-placeholder__shimmer {
  margin: 6px 12px;
  height: 14px;
  flex: 1 1 auto;
  background: linear-gradient(90deg, #f3f4f6 0%, #ececec 50%, #f3f4f6 100%);
  background-size: 200% 100%;
  animation: grid-grouped-shimmer 1.4s linear infinite;
  border-radius: 4px;
}

@keyframes grid-grouped-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
