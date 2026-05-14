<template>
  <div
    class="grid-view__groups"
    :style="{
      paddingTop: `${bufferStartIndex * rowHeight}px`,
    }"
  >
    <div
      v-for="({ groupBy, groupSpans }, index) in groupByValueSets"
      :key="'group-by-' + index"
      :style="{ width: groupBy.width + 'px' }"
    >
      <div
        v-for="(groupSpan, groupSpanIndex) in groupSpans"
        :key="'group-by-span-' + groupSpanIndex"
        class="grid-view__group-span"
        :style="{
          height: `${rowHeight * groupSpan.rowSpan}px`,
        }"
      >
        <GridViewGroup
          :group-by="groupBy"
          :all-fields-in-table="allFieldsInTable"
          :value="groupSpan.value"
          :count="groupSpan.count"
        ></GridViewGroup>
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import GridViewGroup from '@baserow/modules/database/components/view/grid/GridViewGroup'

export default {
  name: 'GridViewGroups',
  components: { GridViewGroup },
  mixins: [gridViewHelpers],
  props: {
    /**
     * All the fields in the table, regardless of the visibility, or whether they
     * should be rendered.
     */
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    groupByValueSets: {
      type: Array,
      required: true,
    },
  },
  computed: {
    rows() {
      return this.$store.getters[`${this.storePrefix}view/grid/getRows`]
    },
    allRows() {
      return this.$store.getters[`${this.storePrefix}view/grid/getAllRows`]
    },
    rowHeight() {
      return this.$store.getters[`${this.storePrefix}view/grid/getRowHeight`]
    },
    bufferStartIndex() {
      return this.$store.getters[
        `${this.storePrefix}view/grid/getBufferStartIndex`
      ]
    },
    activeGroupBys() {
      return this.$store.getters[
        `${this.storePrefix}view/grid/getActiveGroupBys`
      ]
    },
  },
}
</script>
