<template>
  <div
    class="grid-view__group-columns"
    :style="{ width: groupColumnsWidth + 'px', height: totalHeight + 'px' }"
  >
    <GridViewGroupByColumnSpan
      v-for="span in visibleSpans"
      :key="spanKey(span)"
      :span="span"
      :group-by-field="groupByFields[span.depth]"
      :left="levelLefts[span.depth]"
      :width="renderedGroupByWidths[span.depth]"
      :workspace-id="workspaceId"
    />
  </div>
</template>

<script>
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import GridViewGroupByColumnSpan from '@baserow/modules/database/components/view/grid/GridViewGroupByColumnSpan'
import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'

export default {
  name: 'GridViewGroupByColumns',
  components: { GridViewGroupByColumnSpan },
  mixins: [gridViewHelpers],
  props: {
    allFieldsInTable: { type: Array, required: true },
    workspaceId: { type: Number, required: true },
    groupByWidths: { type: Array, default: () => [] },
  },
  computed: {
    renderedGroupByWidths() {
      return this.activeGroupBys.map(
        (groupBy, index) => this.groupByWidths[index] ?? groupBy.width
      )
    },
    groupColumnsWidth() {
      return this.renderedGroupByWidths.reduce(
        (total, width) => total + width,
        0
      )
    },
    groupByFields() {
      return this.activeGroupBys
        .map((groupBy) =>
          this.allFieldsInTable.find((field) => field.id === groupBy.field)
        )
        .filter(Boolean)
    },
    levelLefts() {
      let left = 0
      return this.activeGroupBys.map((_groupBy, index) => {
        const current = left
        left += this.renderedGroupByWidths[index]
        return current
      })
    },
    visibleSpans() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByVisibleItems'
      ](this.groupByFields).filter((item) => item.type === 'groupSpan')
    },
    totalHeight() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByLayout'
      ].totalHeight
    },
  },
  methods: {
    spanKey(span) {
      return `span-${span.depth}-${pathKey(span.path, this.groupByFields)}`
    },
  },
}
</script>
