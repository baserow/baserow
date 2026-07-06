<template>
  <div
    ref="fieldContextAnchor"
    class="grid-view-aggregation"
    :class="{
      'read-only': !userCanMakeAggregations,
    }"
    @click.prevent="
      userCanMakeAggregations &&
      $refs[`fieldContext`].toggle($refs.fieldContextAnchor, 'top', 'right', 10)
    "
  >
    <component
      :is="viewAggregationType.getComponent()"
      v-if="viewAggregationType"
      :loading="loading"
      :aggregation-type="viewAggregationType"
      :value="value"
      :field="field"
    />
    <div
      v-else-if="userCanMakeAggregations"
      class="grid-view-aggregation__empty"
      :class="{
        'grid-view-aggregation__empty--active':
          $refs.fieldContext && $refs.fieldContext.isOpen(),
      }"
    >
      <i class="grid-view-aggregation__empty-icon iconoir-plus"></i>
      {{ $t('common.summarize') }}
    </div>
    <Context ref="fieldContext">
      <ul class="select__items">
        <li
          class="select__item select__item--no-options"
          :class="{ active: !viewAggregationType }"
        >
          <a class="select__item-link" @click="selectAggregation('none')"
            ><div class="select__item-name">
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
          :class="{
            active: viewAggregation === viewAggregationType,
          }"
        >
          <a
            class="select__item-link"
            @click="selectAggregation(viewAggregation.getType())"
            ><div class="select__item-name">
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
import { mapGetters } from 'vuex'

export default {
  name: 'GridViewFieldFooter',
  props: {
    database: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  data() {
    return { pendingValueUpdate: false }
  },
  computed: {
    // Group headers reuse this column's aggregation config in grouped mode.
    groupAggregationsEnabled() {
      return this.$store.getters[this.storePrefix + 'view/grid/isGroupByMode']
    },
    userCanMakeAggregations() {
      return this.$hasPermission(
        'database.table.view.update_field_options',
        this.view,
        this.database.workspace.id
      )
    },
    aggregationType() {
      return this.fieldOptions[this.field.id]?.aggregation_type
    },
    aggregationRawType() {
      return this.fieldOptions[this.field.id]?.aggregation_raw_type
    },
    value() {
      if (
        this.viewAggregationType &&
        this.fieldAggregationData[this.field.id] !== undefined
      ) {
        const { value } = this.fieldAggregationData[this.field.id]

        return this.viewAggregationType.getValue(value, {
          rowCount: this.rowCount,
          field: this.field,
          fieldType: this.fieldType,
        })
      }
      return undefined
    },
    loading() {
      return this.fieldAggregationData[this.field.id]?.loading
    },
    viewAggregationType() {
      if (!this.aggregationType) {
        return null
      }
      try {
        return this.$registry.get('viewAggregation', this.aggregationType)
      } catch (_) {
        // A stale/unknown aggregation type must not crash the grid.
        return null
      }
    },
    viewAggregationTypes() {
      return this.$registry
        .getOrderedList('viewAggregation')
        .filter(
          (agg) => agg.fieldIsCompatible(this.field) && agg.isAllowedInView()
        )
    },
    fieldType() {
      return this.$registry.get('field', this.field.type)
    },
    fieldAggregationData() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getAllFieldAggregationData'
      ]
    },
    fieldOptions() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getAllFieldOptions'
      ]
    },
    rowCount() {
      return this.$store.getters[this.storePrefix + 'view/grid/getCount']
    },
  },
  watch: {
    aggregationRawType(value) {
      if (!value) {
        return
      }
      if (this.pendingValueUpdate) {
        return
      }
      // Skip while a picker already owns the grouped refresh (its spinner is on);
      // remote changes leave it off and still refresh here.
      if (
        this.groupAggregationsEnabled &&
        this.$store.getters[
          this.storePrefix + 'view/grid/getGroupByAggregationsLoading'
        ](this.field.id)
      ) {
        return
      }
      this.$store.dispatch(
        this.storePrefix + 'view/grid/fetchAllFieldAggregationData',
        {
          view: this.view,
        }
      )
    },
  },
  /*beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        fieldAggregationData:
          this.$options.propsData.storePrefix +
          'view/grid/getAllFieldAggregationData',
        fieldOptions:
          this.$options.propsData.storePrefix + 'view/grid/getAllFieldOptions',
        rowCount: this.$options.propsData.storePrefix + 'view/grid/getCount',
      }),
    }
  },*/
  methods: {
    async selectAggregation(newType) {
      this.$refs.fieldContext.hide()

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

      // Only the raw type is server-computed; a display-only change re-renders from
      // the existing value, so skip the spinner and refetch (like the context menu).
      const rawTypeChanged =
        values.aggregation_raw_type !==
        (this.fieldOptions[this.field.id]?.aggregation_raw_type || '')

      const syncGroups = this.groupAggregationsEnabled
      if (syncGroups && rawTypeChanged) {
        // Spin before the optimistic change so the new label never shows the old value.
        this.$store.dispatch(
          this.storePrefix + 'view/grid/setGroupByAggregationsLoading',
          { fieldId: this.field.id }
        )
      }

      // Prevent the watcher to trigger while value is not yet saved on server
      this.pendingValueUpdate = true
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateFieldOptionsOfField',
          {
            field: this.field,
            values,
            readOnly: !this.userCanMakeAggregations,
            skipAggregationRefresh: syncGroups,
          }
        )
      } catch (error) {
        if (syncGroups && rawTypeChanged) {
          this.$store.dispatch(
            this.storePrefix + 'view/grid/setGroupByAggregationsLoading',
            { loading: false }
          )
        }
        throw error
      } finally {
        this.pendingValueUpdate = false
      }

      if (syncGroups && rawTypeChanged) {
        this.$store.dispatch(
          this.storePrefix + 'view/grid/refreshGroupByAggregations',
          {
            view: this.view,
            fields: this.$store.getters['field/getAll'],
            fieldId: this.field.id,
          }
        )
      }
    },
  },
}
</script>
