<template>
  <div
    class="segment-control"
    :class="{
      'segment-control--transparent': transparent,
      'segment-control--icons-only': iconsOnly,
      'segment-control--small': size === 'small',
      'segment-control--large': size === 'large',
      'segment-control--rounded': type === 'rounded',
    }"
  >
    <button
      v-for="(segment, index) in segments"
      :key="index"
      :class="{
        'segment-control__button--active': index === activeIndex,
      }"
      :title="segment.label"
      class="segment-control__button"
      @click.prevent="setActiveIndex(index)"
    >
      <i v-if="segment.icon" :class="segment.icon"></i>
      <span v-if="segment.label" class="segment-control__button-label">{{
        segment.label
      }}</span>
    </button>
  </div>
</template>

<script>
export default {
  name: 'SegmentControl',
  props: {
    /**
     * The segments to display.
     */
    segments: {
      type: Array,
      required: true,
      default: () => [],
    },
    /**
     * The index of the active segment.
     */
    initialActiveIndex: {
      type: Number,
      required: false,
      default: 0,
    },
    /**
     * Whether the segment control background should be transparent. Default is $palette-neutral-50.
     */
    transparent: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the segment control should only display icons.
     */
    iconsOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The size of the segment control.
     */
    size: {
      type: String,
      required: false,
      default: 'regular',
      validator: function (value) {
        return ['regular', 'small', 'large'].includes(value)
      },
    },
    type: {
      type: String,
      required: false,
      default: 'regular',
      validator: function (value) {
        return ['regular', 'rounded'].includes(value)
      },
    },
  },
  data() {
    return {
      activeIndex: this.initialActiveIndex,
    }
  },
  methods: {
    setActiveIndex(index) {
      this.activeIndex = index
      this.$emit('update:activeIndex', index)
    },
    reset() {
      this.activeIndex = this.initialActiveIndex
    },
  },
}
</script>
