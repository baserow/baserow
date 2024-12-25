<template>
  <div class="grid-view__row" :style="{ width: width + 'px', height: '33px' }">
    <div
      class="grid-view__column"
      :style="{ width: width + 'px', height: '33px' }"
    >
      <a
        class="grid-view__add-row"
        :class="{ hover: addHover }"
        @mouseover="setHover(true)"
        @mouseleave="setHover(false)"
        @click="addRow"
        @click.right.prevent="addRows"
      >
        <i
          v-if="includeRowDetails"
          class="grid-view__add-row-icon iconoir-plus"
        ></i>
      </a>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'

export default {
  name: 'GridViewRowAdd',
  mixins: [gridViewHelpers],
  props: {
    visibleFields: {
      type: Array,
      required: true,
    },
    includeRowDetails: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    width() {
      let width = this.visibleFields.reduce(
        (value, field) => this.getFieldWidth(field) + value,
        0
      )
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
        addHover:
          this.$options.propsData.storePrefix + 'view/grid/getAddRowHover',
      }),
    }
  },
  methods: {
    setHover(value) {
      this.$store.dispatch(this.storePrefix + 'view/grid/setAddRowHover', value)
    },
    addRow(event) {
      event.preventFieldCellUnselect = true
      this.$emit('add-row')
    },
    addRows(event) {
      event.preventFieldCellUnselect = true
      this.$emit('add-rows', event)
    },
  },
}
</script>
