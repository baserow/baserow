<template>
  <div
    class="skeleton-block"
    :class="`skeleton-block--${shape}`"
    :style="{ width, height }"
  ></div>
</template>

<script>
/**
 * One pulsing placeholder shape. Compose several of them inside the real layout
 * of the content that is loading, so the page keeps its structure while the data is
 * fetched. Wrap the composition in `.skeleton` to hide it from assistive technology
 * and to switch the pointer off.
 *
 * If the loading state has the same structure as the loaded one, the `v-skeleton`
 * directive is easier because it doesn't need a second template.
 */
export default {
  name: 'SkeletonBlock',
  props: {
    width: {
      type: String,
      required: false,
      default: '100%',
    },
    height: {
      type: String,
      required: false,
      default: '12px',
    },
    shape: {
      type: String,
      required: false,
      default: 'rounded',
      validator(value) {
        return ['rounded', 'square', 'circle'].includes(value)
      },
    },
  },
}
</script>
