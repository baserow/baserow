<template>
  <Context ref="context" class="group-bys" max-height-if-outside-viewport>
    <div class="group-bys__content">
      <div
        v-if="view.group_bys.length === 0"
        v-auto-overflow-scroll
        class="group-bys__none group-bys__none--scrollable"
      >
        <div class="group-bys__none-title">
          {{ $t('viewGroupByContext.noGroupByTitle') }}
        </div>
        <div class="group-bys__none-description">
          {{ $t('viewGroupByContext.noGroupByText') }}
        </div>
      </div>

      <div
        v-if="view.group_bys.length > 0"
        v-auto-overflow-scroll
        class="group-bys__items group-bys__items--scrollable"
      >
        <div
          v-for="(groupBy, index) in view.group_bys"
          :key="groupBy.id"
          class="group-bys__item"
          :class="{
            'group-bys__item--loading': groupBy._.loading,
          }"
          :set="field = getField(groupBy.field)"
        >
          <a
            v-if="!disableGroupBy"
            class="group-bys__remove"
            @click="deleteGroupBy(groupBy)"
          >
            <i class="iconoir-cancel"></i>
          </a>
          <div class="group-bys__description">
            <template v-if="index === 0">{{
              $t('viewGroupByContext.groupBy')
            }}</template>
            <template v-if="index > 0">{{
              $t('viewGroupByContext.thenBy')
            }}</template>
          </div>
          <div class="group-bys__field">
            <Dropdown
              :value="groupBy.field"
              :disabled="disableGroupBy"
              :fixed-items="true"
              class="dropdown--floating"
              @input="updateGroupBy(groupBy, { field: $event })"
            >
              <DropdownItem
                v-for="field in fields"
                :key="'groupBy-field-' + groupBy.id + '-' + field.id"
                :name="field.name"
                :value="field.id"
                :disabled="
                  groupBy.field !== field.id && !isFieldAvailable(field)
                "
              >
              </DropdownItem>
            </Dropdown>
          </div>
          <ViewSortOrder
            :disabled="disableGroupBy"
            :sort-types="getSortTypes(field)"
            :type="groupBy.type"
            :order="groupBy.order"
            @update-order="
              updateGroupBy(groupBy, { order: $event.order, type: $event.type })
            "
          ></ViewSortOrder>
        </div>
        <div v-if="contextWarning" class="group-bys__warning">
          {{ contextWarning }}
        </div>
      </div>
      <div
        v-if="canAddGroupBy || view.group_bys.length > 0"
        class="context__footer"
      >
        <ButtonText
          v-if="canAddGroupBy"
          ref="addDropdownToggle"
          icon="iconoir-plus"
          @click="$refs.addDropdown.toggle($refs.addDropdownToggle.$el)"
        >
          {{ $t('viewGroupByContext.addGroupBy') }}</ButtonText
        >
        <div v-if="canAddGroupBy" class="group-bys__add">
          <Dropdown
            ref="addDropdown"
            :show-input="false"
            :fixed-items="true"
            @input="addGroupBy"
          >
            <DropdownItem
              v-for="field in availableFields"
              :key="field.id"
              :name="field.name"
              :value="field.id"
              :icon="getFieldType(field).iconClass"
            ></DropdownItem>
          </Dropdown>
        </div>
        <div v-if="view.group_bys.length > 0" class="group-bys__footer-actions">
          <ButtonText
            class="group-bys__footer-action"
            type="secondary"
            size="small"
            :disabled="allGroupsCollapsed"
            @click="collapseAll"
          >
            {{ $t('viewGroupByContext.collapseAll') }}
          </ButtonText>
          <ButtonText
            class="group-bys__footer-action"
            type="primary"
            size="small"
            :disabled="allGroupsExpanded"
            @click="expandAll"
          >
            {{ $t('viewGroupByContext.expandAll') }}
          </ButtonText>
        </div>
      </div>
    </div>
  </Context>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import context from '@baserow/modules/core/mixins/context'
import { DEFAULT_SORT_TYPE_KEY } from '@baserow/modules/database/constants'
import ViewSortOrder from '@baserow/modules/database/components/view/ViewSortOrder.vue'

export default {
  name: 'ViewGroupByContext',
  components: { ViewSortOrder },
  mixins: [context],
  props: {
    database: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    disableGroupBy: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['changed'],
  computed: {
    /**
     * Calculates the total amount of available fields.
     */
    availableFieldsLength() {
      return this.fields.filter(this.getCanGroupByInView).length
    },
    availableFields() {
      return this.fields.filter((f) => this.isFieldAvailable(f))
    },
    canAddGroupBy() {
      return (
        this.view.group_bys.length < this.availableFieldsLength &&
        !this.disableGroupBy
      )
    },
    contextWarning() {
      const ownershipType = this.$registry.get(
        'viewOwnershipType',
        this.view.ownership_type
      )
      return ownershipType.getGroupByContextWarning(
        this.view,
        this.fields,
        this.database,
        this.storePrefix
      )
    },
    collapsedGroups() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getCollapsedGroupsForView'
      ](this.view.id)
    },
    collapsedGroupsMode() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getCollapsedGroupsModeForView'
      ](this.view.id)
    },
    /**
     * In collapse-mode, an empty exception list means literally everything is
     * collapsed, so there's nothing left to collapse further.
     */
    allGroupsCollapsed() {
      return (
        this.collapsedGroupsMode === 'collapse' &&
        this.collapsedGroups.length === 0
      )
    },
    /**
     * In expand-mode (default) with no explicit collapses, everything is already
     * expanded.
     */
    allGroupsExpanded() {
      return (
        this.collapsedGroupsMode === 'expand' &&
        this.collapsedGroups.length === 0
      )
    },
  },
  methods: {
    getFieldType(field) {
      return this.$registry.get('field', field.type)
    },
    getCanGroupByInView(field) {
      return this.getFieldType(field).getCanGroupByInView(field)
    },
    getField(fieldId) {
      for (const i in this.fields) {
        if (this.fields[i].id === fieldId) {
          return this.fields[i]
        }
      }
      return undefined
    },
    isFieldAvailable(field) {
      const allFieldIds = this.view.group_bys.map((groupBy) => groupBy.field)
      return this.getCanGroupByInView(field) && !allFieldIds.includes(field.id)
    },
    async addGroupBy(fieldId) {
      this.$refs.addDropdown.hide()

      try {
        await this.$store.dispatch('view/createGroupBy', {
          view: this.view,
          values: {
            field: fieldId,
            value: 'ASC',
            type: DEFAULT_SORT_TYPE_KEY,
          },
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async deleteGroupBy(groupBy) {
      try {
        await this.$store.dispatch('view/deleteGroupBy', {
          view: this.view,
          groupBy,
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateGroupBy(groupBy, values) {
      if (this.disableGroupBy) {
        return
      }

      // If the field has changed, the type might not be compatible anymore. If so,
      // then we're falling back on the default sort type.
      if (values.field) {
        const sortType = values.type || groupBy.type
        const field = this.getField(values.field)
        const fieldType = this.getFieldType(field)
        const sortTypes = fieldType.getSortTypes(field)
        if (!Object.prototype.hasOwnProperty.call(sortTypes, sortType)) {
          values.type = DEFAULT_SORT_TYPE_KEY
        }
      }

      try {
        await this.$store.dispatch('view/updateGroupBy', {
          groupBy,
          values,
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    getSortTypes(field) {
      return this.getFieldType(field).getSortTypes(field)
    },
    async collapseAll() {
      this.$store.dispatch(this.storePrefix + 'view/grid/collapseAllGroups', {
        viewId: this.view.id,
        fields: this.fields,
      })
      this.$emit('changed')
    },
    async expandAll() {
      this.$store.dispatch(this.storePrefix + 'view/grid/expandAllGroups', {
        viewId: this.view.id,
      })
      this.$emit('changed')
    },
  },
}
</script>
