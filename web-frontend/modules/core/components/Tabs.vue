<template>
  <div
    class="tabs"
    :class="{
      'tabs--full-height': fullHeight,
      'tabs--large-offset': largeOffset,
      'tabs--large': large,
      'tabs--header-nopadding': headerNoPadding,
      'tabs--content-no-x-padding': contentNoXPadding,
      'tabs--content-no-padding': contentNoPadding,
      'tabs--grow-items': growItems,
      'tabs--rounded': rounded,
    }"
  >
    <ul class="tabs__header">
      <li
        v-for="(tab, index) in tabs"
        :key="`${tab.title} ${tab.tooltip}`"
        v-tooltip="tab.tooltip"
        :tooltip-position="tab.tooltipPosition"
        class="tabs__item"
        :class="{
          'tabs__item--active': isActive(index),
          'tabs__item--disabled': tab.disabled,
        }"
        :data-highlight="tab.highlight"
        @click="
          tab.disabled ? $emit('click-disabled', index) : selectTab(index)
        "
      >
        <a
          :href="getHref(index)"
          class="tabs__link"
          :class="{ 'tabs__link--disabled': tab.disabled }"
          @click.prevent
        >
          <i v-if="tab.icon" :class="tab.icon"></i>
          {{ tab.title }}
          <i v-if="tab.appendIcon" :class="tab.appendIcon"></i>
        </a>
      </li>
    </ul>

    <slot></slot>
  </div>
</template>

<script>
export default {
  name: 'Tabs',
  props: {
    /**
     * The index of the selected tab.
     */
    selectedIndex: {
      type: Number,
      required: false,
      default: 0,
    },
    /**
     * Whether the tabs should take the full height of the parent.
     */
    fullHeight: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The Vue route object. If provided the tabs will be used for navigation.
     * and the active tab will be set according to the current route.
     * The child Tab components should have a `to` prop set.
     */
    route: {
      type: Object,
      required: false,
      default: null,
    },
    /**
     * Whether the tabs header container should add some extra space to the left.
     */
    largeOffset: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the tabs are the larger variant.
     */
    large: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Removes the padding from the tabs container and header.
     */
    headerNoPadding: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Removes the left and right padding from the tabs container only.
     */
    contentNoXPadding: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Removes padding (x and y) from the tabs container only.
     */
    contentNoPadding: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the tabs header items should grow to use all the available space.
     */
    growItems: {
      type: Boolean,
      required: false,
      default: false,
    },
    tabItems: {
      type: [Array, null],
      required: false,
      default: null,
    },
    rounded: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      internalSelectedIndex: 0, // In case the prop isn't used by a parent
      tabs: [], // all the tabs
    }
  },
  watch: {
    selectedIndex: {
      handler(i) {
        if (!this.route && i !== undefined) {
          this.internalSelectedIndex = i
        }
      },
      immediate: true,
    },
  },
  created() {
    if (this.tabItems) {
      this.tabs = this.tabItems
    } else {
      this.tabs = this.$children
    }
  },
  mounted() {
    if (this.route) {
      this.tabs.forEach((tab) => {
        tab.isActive = this.route.name === tab.to.name
      })
    } else this.selectTab(this.internalSelectedIndex)
  },
  methods: {
    isActive(i) {
      if (this.route) return this.route.name === this.tabs[i].to.name
      else return this.internalSelectedIndex === i
    },
    getHref(i) {
      if (this.route) {
        const tab = this.tabs[i]
        return !tab.disabled ? this.$router.match(tab.to).path : null
      }
      return null
    },
    selectTab(i) {
      if (this.route) {
        this.$emit('update:selectedIndex', i)
        this.$router.push(this.tabs[i].to)
      } else {
        this.$emit('update:selectedIndex', i)
        this.internalSelectedIndex = i
      }
      if (!this.tabItems) {
        this.tabs.forEach((tab, index) => {
          tab.isActive = index === i
        })
      }
    },
  },
}
</script>
