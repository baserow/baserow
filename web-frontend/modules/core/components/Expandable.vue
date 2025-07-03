<template>
  <div
    class="expandable"
    :class="{
      'expandable--expanded': expanded,
    }"
  >
    <div
      class="expandable__header"
      :class="{
        'expandable__header--card': card,
        'expandable--toggle-on-click': toggleOnClick,
      }"
      @click="onClick()"
    >
      <slot name="header" :toggle="toggle" :expanded="expanded" />
    </div>
    <div
      v-if="expanded"
      class="expandable__content"
      :class="{ 'expandable__content--card': card }"
    >
      <slot :toggle="toggle" :expanded="expanded" />
    </div>
  </div>
</template>

<script>
export default {
  name: 'Expandable',
  props: {
    defaultExpanded: {
      type: Boolean,
      required: false,
      default: false,
    },
    forceExpanded: {
      type: Boolean,
      required: false,
      default: null,
    },
    card: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * If true, then clicking on any part of the heading will toggle the content
     */
    toggleOnClick: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return { expandedState: this.defaultExpanded }
  },
  computed: {
    expanded() {
      if (this.forceExpanded !== null) {
        return this.forceExpanded
      } else {
        return this.expandedState
      }
    },
  },
  methods: {
    onClick() {
      if (this.toggleOnClick) {
        this.toggle()
      }

      this.$emit('toggle')
    },
    toggle() {
      this.expandedState = !this.expandedState
    },
  },
}
</script>
