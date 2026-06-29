<template>
  <div
    v-if="hasValue || editable"
    ref="anchor"
    class="grid-view-aggregation grid-view__group-by-banner-aggregation"
    :class="{ 'read-only': !editable }"
    :title="titleText"
    @click.prevent="
      editable && $refs.context.toggle($refs.anchor, 'top', 'right', 10)
    "
  >
    <component
      :is="viewAggregationType.getComponent()"
      v-if="hasValue"
      :aggregation-type="viewAggregationType"
      :value="value"
      :field="field"
      :loading="loading"
    />
    <div
      v-else-if="loading && viewAggregationType"
      class="grid-view__group-by-banner-aggregation-loading"
    ></div>
    <!-- Only unconfigured columns offer the picker; a configured column with no
    per-group value (e.g. distribution) shows nothing. -->
    <div
      v-else-if="!viewAggregationType"
      class="grid-view-aggregation__empty grid-view__group-by-banner-aggregation-empty"
      :class="{
        'grid-view-aggregation__empty--active':
          $refs.context && $refs.context.isOpen(),
      }"
    >
      <i class="grid-view-aggregation__empty-icon iconoir-plus"></i>
      {{ $t('common.summarize') }}
    </div>
    <Context ref="context">
      <ul class="select__items">
        <li
          class="select__item select__item--no-options"
          :class="{ active: !viewAggregationType }"
        >
          <a class="select__item-link" @click="selectAggregation('none')">
            <div class="select__item-name">
              <span class="select__item-name-text">{{
                $t('common.none')
              }}</span>
            </div>
          </a>
          <i
            v-if="!viewAggregationType"
            class="select__item-active-icon iconoir-check"
          ></i>
        </li>
        <li
          v-for="viewAggregation in viewAggregationTypes"
          :key="viewAggregation.getType()"
          class="select__item select__item--no-options"
          :class="{ active: viewAggregation === viewAggregationType }"
        >
          <a
            class="select__item-link"
            @click="selectAggregation(viewAggregation.getType())"
          >
            <div class="select__item-name">
              <span class="select__item-name-text">{{
                viewAggregation.getName()
              }}</span>
            </div>
          </a>
          <i
            v-if="viewAggregation === viewAggregationType"
            class="select__item-active-icon iconoir-check"
          ></i>
        </li>
      </ul>
    </Context>
  </div>
</template>

<script>
export default {
  name: 'GridViewGroupByAggregation',
  props: {
    view: {
      type: Object,
      required: true,
    },
    workspaceId: {
      type: null,
      default: null,
    },
    field: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
    // The raw, server-computed aggregation value for this group, or undefined when
    // the field has no per-group value (e.g. an unsupported aggregation type).
    rawValue: {
      type: null,
      default: undefined,
    },
    // This group's row count, used as the percentage/total context, mirroring the
    // grid footer.
    rowCount: {
      type: Number,
      default: 0,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['change'],
  computed: {
    fieldOptions() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getAllFieldOptions'
      ]
    },
    aggregationType() {
      return this.fieldOptions[this.field.id]?.aggregation_type
    },
    viewAggregationType() {
      if (!this.aggregationType) {
        return null
      }
      try {
        const aggregation = this.$registry.get(
          'viewAggregation',
          this.aggregationType
        )
        // A table-level-only aggregation (e.g. distribution) shares this field's
        // footer config but has no per-group value, so resolve it to null here to
        // keep the group cell empty instead of rendering against a stale value.
        return aggregation.isAllowedInGroupBy() ? aggregation : null
      } catch (_) {
        return null
      }
    },
    viewAggregationTypes() {
      return this.$registry
        .getOrderedList('viewAggregation')
        .filter(
          (agg) =>
            agg.fieldIsCompatible(this.field) &&
            agg.isAllowedInView() &&
            agg.isAllowedInGroupBy()
        )
    },
    fieldType() {
      return this.$registry.get('field', this.field.type)
    },
    editable() {
      return this.$hasPermission(
        'database.table.view.update_field_options',
        this.view,
        this.workspaceId
      )
    },
    hasValue() {
      return this.viewAggregationType !== null && this.rawValue !== undefined
    },
    // Full label + value tooltip; the label is clipped when the column is narrow.
    titleText() {
      if (!this.hasValue) {
        return null
      }
      return `${this.viewAggregationType.getShortName()} ${this.value}`
    },
    value() {
      if (!this.viewAggregationType) {
        return undefined
      }
      return this.viewAggregationType.getValue(this.rawValue, {
        rowCount: this.rowCount,
        field: this.field,
        fieldType: this.fieldType,
      })
    },
  },
  methods: {
    async selectAggregation(newType) {
      this.$refs.context.hide()

      const values = {
        aggregation_type: '',
        aggregation_raw_type: '',
      }

      if (newType !== 'none') {
        const selectedAggregation = this.$registry.get(
          'viewAggregation',
          newType
        )
        values.aggregation_type = newType
        values.aggregation_raw_type = selectedAggregation.getRawType()
      }

      // Spin before the optimistic change so the new label never shows the old value.
      this.$store.dispatch(
        this.storePrefix + 'view/grid/setGroupByAggregationsLoading',
        { fieldId: this.field.id }
      )
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateFieldOptionsOfField',
          {
            field: this.field,
            values,
            readOnly: !this.editable,
            skipAggregationRefresh: true,
          }
        )
      } catch (error) {
        this.$store.dispatch(
          this.storePrefix + 'view/grid/setGroupByAggregationsLoading',
          { loading: false }
        )
        throw error
      }
      // The aggregation values are computed server-side, so the visible group tree
      // must be refetched to reflect the new function.
      this.$emit('change')
    },
  },
}
</script>
