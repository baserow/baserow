<template>
  <div
    v-if="isActive"
    class="tab"
    :class="{
      'tab--no-scroll': noScroll,
    }"
    @click="$emit('click', $event)"
  >
    <slot></slot>
  </div>
</template>

<script>
export default {
  name: 'Tab',
  props: {
    title: {
      type: String,
      default: 'Tab',
    },
    disabled: {
      type: Boolean,
      default: () => false,
    },
    tooltip: {
      type: String,
      default: null,
      required: false,
    },
    to: {
      type: Object,
      default: () => undefined,
      required: false,
    },
    icon: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * If true it will not scroll the content of the tab.
     */
    noScroll: {
      type: Boolean,
      default: false,
      required: false,
    },
  },
  data() {
    return {
      isActive: false,
    }
  },
}
</script>
