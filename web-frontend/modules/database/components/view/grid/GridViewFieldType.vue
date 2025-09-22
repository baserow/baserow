<template>
  <div
    class="grid-view__column"
    :class="{
      'grid-view__column--filtered':
        !view.filters_disabled &&
        view.filters.findIndex((filter) => filter.field === field.id) !== -1,
      'grid-view__column--grouped':
        view.group_bys.findIndex((groupBy) => groupBy.field === field.id) !==
        -1,
      'grid-view__column--sorted':
        view.sortings.findIndex((sort) => sort.field === field.id) !== -1,
    }"
    :style="{ width: width + 'px' }"
    @mousedown="startDragging($event, field)"
  >
    <div
      class="grid-view__description"
      :class="{ 'grid-view__description--loading': field._.loading }"
    >
      <div class="grid-view__description-icon-container">
        <i :class="`grid-view__description-icon ${field._.type.iconClass}`"></i>
        <i
          v-if="synced"
          v-tooltip="
            table.data_sync.two_way_sync && canWriteFieldValues
              ? $t('gridViewFieldType.dataSyncFieldTwoWaySync')
              : $t('gridViewFieldType.dataSyncField')
          "
          class="grid-view__description-extra-icon iconoir-data-transfer-down"
        ></i>
        <i
          v-else-if="!canWriteFieldValues"
          v-tooltip="$t('gridViewFieldType.noWriteValues')"
          class="grid-view__description-extra-icon iconoir-lock"
        ></i>
      </div>

      <div
        class="grid-view__description-name"
        :title="field.name + (synced ? ' (synced)' : '')"
      >
        <span ref="quickEditLink" @dblclick="handleQuickEdit()">
          {{ field.name }}
        </span>
      </div>
      <div v-if="field.error" class="grid-view__description-icon-error">
        <i v-tooltip="field.error" class="iconoir-warning-triangle"></i>
      </div>
      <span class="grid-view__description-options">
        <component
          :is="component"
          v-for="(component, i) in getIconsBefore()"
          :key="i"
          :workspace="database.workspace"
          :database="database"
          :table="table"
          :view="view"
          :field="field"
        />

        <HelpIcon
          v-if="field.description"
          :tooltip="field.description || ''"
          :tooltip-content-type="'plain'"
          :tooltip-content-classes="[
            'tooltip__content--expandable',
            'tooltip__content--expandable-plain-text',
          ]"
          :icon="'info-empty'"
          :tooltip-duration="0.2"
        />

        <a
          v-if="!readOnly && showFieldContext"
          ref="contextLink"
          class="grid-view__description-icon-trigger"
          @click="$refs.context.toggle($refs.contextLink, 'bottom', 'right', 0)"
          @mousedown.stop
        >
          <i class="iconoir-nav-arrow-down"></i>
        </a>
      </span>

      <FieldContext
        v-if="!readOnly"
        ref="context"
        :database="database"
        :table="table"
        :view="view"
        :field="field"
        :all-fields-in-table="allFieldsInTable"
        @update="$emit('refresh', $event)"
        @delete="$emit('refresh')"
      >
        <li
          v-if="
            !field.primary &&
            !readOnly &&
            $hasPermission(
              'database.table.create_field',
              table,
              database.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            ref="insertLeftLink"
            class="context__menu-item-link"
            @click="
              $refs.insertFieldContext.toggle($refs.insertLeftLink, 'left')
            "
          >
            <i class="context__menu-item-icon iconoir-arrow-left"></i>
            {{ $t('gridViewFieldType.insertLeft') }}
          </a>
        </li>
        <li
          v-if="
            !field.primary &&
            !readOnly &&
            $hasPermission(
              'database.table.create_field',
              table,
              database.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            ref="insertRightLink"
            class="context__menu-item-link"
            @click="
              $refs.insertFieldContext.toggle($refs.insertRightLink, 'right')
            "
          >
            <i class="context__menu-item-icon iconoir-arrow-right"></i>
            {{ $t('gridViewFieldType.insertRight') }}
          </a>
          <InsertFieldContext
            ref="insertFieldContext"
            :table="table"
            :view="view"
            :from-field="field"
            :all-fields-in-table="allFieldsInTable"
            :database="database"
            @field-created="$emit('field-created', $event)"
            @move-field="moveField($event)"
          ></InsertFieldContext>
        </li>
        <li
          v-if="
            !readOnly &&
            $hasPermission(
              'database.table.field.duplicate',
              field,
              database.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click=";[$refs.duplicateFieldModal.toggle(), $refs.context.hide()]"
          >
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('gridViewFieldType.duplicate') }}
          </a>
          <DuplicateFieldModal
            ref="duplicateFieldModal"
            :table="table"
            :from-field="field"
            :all-fields-in-table="allFieldsInTable"
            @field-created="$emit('field-created', $event)"
            @move-field="moveField($event)"
          ></DuplicateFieldModal>
        </li>
        <li />
        <li
          v-if="
            canFilter &&
            $hasPermission(
              'database.table.view.create_filter',
              view,
              database.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click="createFilter($event, view, field)"
          >
            <i class="context__menu-item-icon iconoir-filter"></i>
            {{ $t('gridViewFieldType.createFilter') }}
          </a>
        </li>
        <li
          v-if="
            getCanSortInView(field) &&
            $hasPermission(
              'database.table.view.create_sort',
              view,
              database.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click="createSort($event, view, field, 'ASC')"
          >
            <i class="context__menu-item-icon iconoir-sort-down"></i>
            {{ $t('gridViewFieldType.sortField') }}
            <template v-if="getSortIndicator(field, 0) === 'text'">{{
              getSortIndicator(field, 1)
            }}</template>
            <i
              v-if="getSortIndicator(field, 0) === 'icon'"
              :class="getSortIndicator(field, 1)"
            ></i>
            <i class="iconoir-arrow-right"></i>
            <template v-if="getSortIndicator(field, 0) === 'text'">{{
              getSortIndicator(field, 2)
            }}</template>
            <i
              v-if="getSortIndicator(field, 0) === 'icon'"
              :class="getSortIndicator(field, 2)"
            ></i>
          </a>
        </li>
        <li
          v-if="
            getCanSortInView(field) &&
            $hasPermission(
              'database.table.view.create_sort',
              view,
              database.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click="createSort($event, view, field, 'DESC')"
          >
            <i class="context__menu-item-icon iconoir-sort-down"></i>
            {{ $t('gridViewFieldType.sortField') }}
            <template v-if="getSortIndicator(field, 0) === 'text'">{{
              getSortIndicator(field, 2)
            }}</template>
            <i
              v-if="getSortIndicator(field, 0) === 'icon'"
              :class="getSortIndicator(field, 2)"
            ></i>
            <i class="iconoir-arrow-right"></i>
            <template v-if="getSortIndicator(field, 0) === 'text'">{{
              getSortIndicator(field, 1)
            }}</template>
            <i
              v-if="getSortIndicator(field, 0) === 'icon'"
              :class="getSortIndicator(field, 1)"
            ></i>
          </a>
        </li>
        <li
          v-if="
            !field.primary &&
            $hasPermission(
              'database.table.view.update_field_options',
              view,
              database.workspace.id
            )
          "
          class="context__menu-item"
        >
          <a class="context__menu-item-link" @click="hide($event, view, field)">
            <i class="context__menu-item-icon iconoir-eye-off"></i>
            {{ $t('gridViewFieldType.hideField') }}
          </a>
        </li>
      </FieldContext>
      <HorizontalResize
        v-if="includeFieldWidthHandles"
        class="grid-view__description-width"
        :width="width"
        :min="GRID_VIEW_MIN_FIELD_WIDTH"
        @move="moveFieldWidth(field, $event)"
        @update="updateFieldWidth(field, view, database, readOnly, $event)"
      ></HorizontalResize>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'

import FieldContext from '@baserow/modules/database/components/field/FieldContext'
import InsertFieldContext from '@baserow/modules/database/components/field/InsertFieldContext'
import DuplicateFieldModal from '@baserow/modules/database/components/field/DuplicateFieldModal'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import { DEFAULT_SORT_TYPE_KEY } from '@baserow/modules/database/constants'

export default {
  name: 'GridViewFieldType',
  components: {
    HorizontalResize,
    FieldContext,
    InsertFieldContext,
    DuplicateFieldModal,
  },
  mixins: [gridViewHelpers],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    includeFieldWidthHandles: {
      type: Boolean,
      required: false,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      dragging: false,
    }
  },
  computed: {
    width() {
      return this.getFieldWidth(this.field)
    },
    canFilter() {
      const filters = Object.values(this.$registry.getAll('viewFilter'))
      for (const type in filters) {
        if (filters[type].fieldIsCompatible(this.field)) {
          return true
        }
      }
      return false
    },
    showFieldContext() {
      return (
        this.$hasPermission(
          'database.table.create_field',
          this.table,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.view.create_filter',
          this.view,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.view.create_sort',
          this.view,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.view.update_field_options',
          this.view,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.field.duplicate',
          this.field,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.field.update',
          this.field,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.field.delete',
          this.field,
          this.database.workspace.id
        )
      )
    },
    synced() {
      if (!this.table.data_sync) {
        return false
      }
      return this.table.data_sync.synced_properties.some((p) => {
        return p.field_id === this.field.id
      })
    },
    canWriteFieldValues() {
      return this.$registry
        .get('field', this.field.type)
        .canWriteFieldValues(this.field)
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        fieldOptions:
          this.$options.propsData.storePrefix + 'view/grid/getAllFieldOptions',
      }),
    }
  },
  methods: {
    moveField($event) {
      this.$emit('move-field', $event)
      this.$refs.context.hide()
    },
    async handleQuickEdit() {
      if (this.readOnly) return false
      await this.$refs.context.toggle(
        this.$refs.quickEditLink,
        'bottom',
        'left',
        0
      )
      this.$refs.context.showUpdateFieldContext()
    },
    quickEditField($event) {
      this.$emit('updated', $event)
      this.$refs.context.hide()
    },
    async createFilter(event, view, field) {
      // Prevent the event from propagating to the body so that it does not close the
      // view filter context menu right after it has been opened. This is due to the
      // click outside event that is fired there.
      event.stopPropagation()
      event.preventDefault()
      this.$refs.context.hide()

      try {
        await this.$store.dispatch('view/createFilter', {
          view,
          field,
          values: {
            field: field.id,
          },
        })
        this.$emit('refresh')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async createSort(event, view, field, order) {
      // Prevent the event from propagating to the body so that it does not close the
      // view filter context menu right after it has been opened. This is due to the
      // click outside event that is fired there.
      event.stopPropagation()
      event.preventDefault()
      this.$refs.context.hide()

      const sort = view.sortings.find((sort) => sort.field === this.field.id)
      const values = {
        field: field.id,
        order,
      }

      try {
        if (sort === undefined) {
          await this.$store.dispatch('view/createSort', {
            view,
            field,
            values: { ...values, type: DEFAULT_SORT_TYPE_KEY },
          })
        } else {
          await this.$store.dispatch('view/updateSort', {
            sort,
            values,
          })
        }

        this.$emit('refresh')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async hide(event, view, field) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateFieldOptionsOfField',
          {
            field,
            values: { hidden: true },
            oldValues: { hidden: false },
            readOnly: !this.$hasPermission(
              'database.table.view.update_field_options',
              this.view,
              this.database.workspace.id
            ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    startDragging(event, field) {
      this.$emit('dragging', { field, event })
    },
    getSortIndicator(field, index) {
      return this.$registry.get('field', field.type).getSortIndicator(field)[
        index
      ]
    },
    getCanSortInView(field) {
      return this.$registry.get('field', field.type).getCanSortInView(field)
    },

    getIconsBefore() {
      const opts = Object.values(this.$registry.getAll('plugin'))
        .reduce((components, plugin) => {
          components = components.concat(
            plugin.getGridViewFieldTypeIconsBefore(
              this.database.workspace,
              this.view,
              this.field
            )
          )
          return components
        }, [])
        .filter((component) => component !== null)
      return opts
    },
  },
}
</script>
