<template>
  <div v-if="isActive" class="tab" @click="$emit('click', $event)">
    <slot></slot>
  </div>
</template>

<script>
export default {
  name: 'Tab',
  inject: {
    tabsProvider: {
      default: null,
    },
  },
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
    tooltipPosition: {
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
    appendIcon: {
      type: String,
      required: false,
      default: null,
    },
    highlight: {
      type: [String, null],
      required: false,
      default: null,
    },
  },
  emits: ['click'],
  data() {
    return {
      isActive: false,
    }
  },
  mounted() {
    if (this.tabsProvider) {
      this.tabsProvider.registerTab(this)
    }
  },
  beforeUnmount() {
    if (this.tabsProvider) {
      this.tabsProvider.unregisterTab(this)
    }
  },
}
</script>
