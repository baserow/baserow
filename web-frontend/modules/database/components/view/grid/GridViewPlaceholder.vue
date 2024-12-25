<template>
  <div
    class="grid-view__placeholder"
    :style="{
      height: placeholderHeight + 'px',
      width: placeholderWidth + 'px',
    }"
  >
    <div
      v-if="includeGroupBy"
      class="grid-view__placeholder-groups"
      :style="{ width: groupByWidth + 'px' }"
    ></div>
    <template v-if="includeRowDetails || visibleFields.length > 0">
      <div
        v-for="(value, index) in placeholderPositions"
        :key="'placeholder-column-' + index"
        class="grid-view__placeholder-column"
        :style="{ left: value - 1 + 'px' }"
      ></div>
    </template>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'

export default {
  name: 'GridViewPlaceholder',
  mixins: [gridViewHelpers],
  props: {
    visibleFields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    includeRowDetails: {
      type: Boolean,
      required: true,
    },
    includeGroupBy: {
      type: Boolean,
      required: false,
      default: () => false,
    },
  },
  computed: {
    groupByWidth() {
      return this.includeGroupBy ? this.activeGroupByWidth : 0
    },
    /**
     * Calculate the left positions of the placeholder columns. These are the gray
     * vertical lines that are always visible, even when the data hasn't loaded yet.
     */
    placeholderPositions() {
      let last = this.groupByWidth
      last += this.includeRowDetails ? this.gridViewRowDetailsWidth : 0
      const placeholderPositions = {}
      this.visibleFields.forEach((field) => {
        last += this.getFieldWidth(field)
        placeholderPositions[field.id] = last
      })
      return placeholderPositions
    },
    placeholderWidth() {
      let width = this.visibleFields.reduce(
        (value, field) => this.getFieldWidth(field) + value,
        0
      )
      width += this.groupByWidth
      if (this.includeRowDetails) {
        width += this.gridViewRowDetailsWidth
      }
      return width
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        placeholderHeight:
          this.$options.propsData.storePrefix +
          'view/grid/getPlaceholderHeight',
        activeGroupBys:
          this.$options.propsData.storePrefix + 'view/grid/getActiveGroupBys',
      }),
    }
  },
}
</script>
