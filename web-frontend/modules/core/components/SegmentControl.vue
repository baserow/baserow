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
        'segment-control__button--active': index === currentActiveIndex,
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
      default: () => [],
    },
    /**
     * The index of the active segment (v-model:activeIndex).
     */
    activeIndex: {
      type: Number,
      required: false,
      default: null,
    },
    /**
     * The initial index of the active segment (used when activeIndex prop is not provided).
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
  emits: ['update:activeIndex'],
  data() {
    return {
      internalActiveIndex:
        this.activeIndex !== null ? this.activeIndex : this.initialActiveIndex,
    }
  },
  computed: {
    currentActiveIndex() {
      return this.activeIndex !== null
        ? this.activeIndex
        : this.internalActiveIndex
    },
  },
  watch: {
    activeIndex(newVal) {
      if (newVal !== null) {
        this.internalActiveIndex = newVal
      }
    },
  },
  methods: {
    setActiveIndex(index) {
      this.internalActiveIndex = index
      this.$emit('update:activeIndex', index)
    },
    reset() {
      this.internalActiveIndex =
        this.activeIndex !== null ? this.activeIndex : this.initialActiveIndex
    },
  },
}
</script>
