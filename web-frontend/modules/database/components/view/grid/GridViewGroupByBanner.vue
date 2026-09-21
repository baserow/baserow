<template>
  <div
    class="grid-view__group-by-banner"
    :class="{
      'grid-view__group-by-banner--collapsed': item.collapsed,
      'grid-view__group-by-banner--gap-above': item.gapAbove,
    }"
    :style="{
      top: item.y + 'px',
      height: item.height + 'px',
      width: width + 'px',
    }"
    :data-collapsed="item.collapsed ? 'true' : 'false'"
  >
    <div
      v-if="includeRowDetails"
      class="grid-view__group-by-banner-chevron-lane"
      :style="{
        width: rowDetailsWidth + 'px',
        paddingLeft: indentPx + 'px',
      }"
    >
      <button
        type="button"
        class="grid-view__group-by-banner-toggle"
        :aria-expanded="!item.collapsed"
        :aria-label="
          item.collapsed
            ? $t('gridViewGroupByBanner.expandGroup')
            : $t('gridViewGroupByBanner.collapseGroup')
        "
        @click="$emit('toggle', item.path)"
      >
        <i
          :class="
            item.collapsed
              ? 'iconoir-nav-arrow-right'
              : 'iconoir-nav-arrow-down'
          "
        />
      </button>
    </div>
    <div
      v-for="(field, index) in visibleFields"
      :key="field.id"
      class="grid-view__group-by-banner-field"
      :class="{
        'grid-view__group-by-banner-field--primary':
          includeRowDetails && index === 0,
      }"
      :style="bannerFieldStyle(field, index)"
    >
      <template v-if="includeRowDetails && index === 0">
        <div class="grid-view__group-by-banner-stack">
          <div class="grid-view__group-by-banner-label">
            {{ fieldNameLabel }}
          </div>
          <div class="grid-view__group-by-banner-value">
            <span
              v-if="isEmptyValue"
              class="grid-view__group-by-banner-value-empty"
            >
              {{ emptyValueLabel }}
            </span>
            <component
              :is="groupByComponent"
              v-else-if="groupByComponent"
              :field="groupByField"
              :value="rowValueForGroup"
              :workspace-id="workspaceId"
            />
            <span v-else class="grid-view__group-by-banner-value-text">
              {{ fallbackValueText }}
            </span>
          </div>
        </div>
        <div class="grid-view__group-by-banner-count">
          {{ item.rowCount }}
        </div>
      </template>
      <GridViewGroupByAggregation
        v-else-if="aggregationsEnabled"
        :view="view"
        :workspace-id="workspaceId"
        :field="field"
        :store-prefix="storePrefix"
        :raw-value="aggregationValueFor(field)"
        :row-count="item.rowCount"
        :aggregation-row-count="item.aggregationRowCount"
        :loading="aggregationLoadingFor(field.id) || groupAggregationsLoading"
        @change="$emit('aggregation-changed', field.id)"
      />
    </div>
    <div
      v-for="(position, index) in separatorPositions"
      :key="'separator-' + index"
      class="grid-view__group-by-banner-separator"
      :style="{ left: position - 1 + 'px' }"
    />
  </div>
</template>

<script>
import {
  groupBannerIndentPx,
  pathKey,
} from '@baserow/modules/database/utils/gridGroupByRender'
import GridViewGroupByAggregation from '@baserow/modules/database/components/view/grid/GridViewGroupByAggregation'
import gridViewGroupByValue from '@baserow/modules/database/mixins/gridViewGroupByValue'

export default {
  name: 'GridViewGroupByBanner',
  components: { GridViewGroupByAggregation },
  mixins: [gridViewGroupByValue],
  props: {
    item: {
      type: Object,
      required: true,
    },
    groupByFields: {
      type: Array,
      required: true,
    },
    includeRowDetails: {
      type: Boolean,
      default: false,
    },
    rowDetailsWidth: {
      type: Number,
      default: 72,
    },
    workspaceId: {
      type: null,
      default: null,
    },
    width: {
      type: Number,
      required: true,
    },
    visibleFields: {
      type: Array,
      default: () => [],
    },
    fieldWidths: {
      type: Object,
      default: () => ({}),
    },
    view: {
      type: Object,
      default: null,
    },
    storePrefix: {
      type: String,
      default: '',
    },
  },
  emits: ['toggle', 'aggregation-changed'],
  computed: {
    aggregationsEnabled() {
      return this.storePrefix !== '' && this.view !== null
    },
    aggregationLoadingFor() {
      if (this.storePrefix === '') {
        return () => false
      }
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByAggregationsLoading'
      ]
    },
    // Spin while this group's post-insertion aggregation refresh is in flight, to
    // avoid showing a value derived from the already-bumped row count.
    groupAggregationsLoading() {
      if (this.storePrefix === '') {
        return false
      }
      const loadingPaths =
        this.$store.getters[
          this.storePrefix + 'view/grid/getGroupByAggregationsLoadingPaths'
        ]
      return loadingPaths.includes(pathKey(this.item.path, this.groupByFields))
    },
    groupByField() {
      return this.groupByFields[this.item.depth]
    },
    groupPath() {
      return this.item.path
    },
    groupDisplay() {
      return this.item.display
    },
    fieldNameLabel() {
      return this.groupByField?.name || ''
    },
    emptyValueLabel() {
      return this.$t('gridViewGroupByBanner.emptyValue')
    },
    indentPx() {
      return groupBannerIndentPx(
        this.item.depth,
        this.groupByFields.length,
        this.rowDetailsWidth
      )
    },
    separatorPositions() {
      const positions = []
      let x = 0

      // Skip the id/primary boundary: data rows leave the row-details column
      // borderless, so the banner must not draw a divider there either.
      if (this.includeRowDetails) {
        x += this.rowDetailsWidth
      }

      this.visibleFields.slice(0, -1).forEach((field) => {
        x += this.fieldWidths[field.id] || 0
        positions.push(x)
      })
      return positions
    },
  },
  methods: {
    aggregationValueFor(field) {
      if (!this.item.aggregations) {
        return undefined
      }
      return this.item.aggregations[`field_${field.id}`]
    },
    bannerFieldStyle(field, index) {
      const style = { width: (this.fieldWidths[field.id] || 0) + 'px' }
      if (this.includeRowDetails && index === 0) {
        // Indent the field-name block in lockstep with the chevron.
        style.paddingLeft = this.indentPx + 'px'
      }
      return style
    },
  },
}
</script>
