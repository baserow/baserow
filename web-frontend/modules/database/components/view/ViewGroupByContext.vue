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
          :set="(field = getField(groupBy.field))"
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
      </div>
      <div
        v-if="view.group_bys.length < availableFieldsLength && !disableGroupBy"
        class="context__footer"
      >
        <ButtonText
          ref="addDropdownToggle"
          icon="iconoir-plus"
          @click="$refs.addDropdown.toggle($refs.addDropdownToggle.$el)"
        >
          {{ $t('viewGroupByContext.addGroupBy') }}</ButtonText
        >
        <div class="group-bys__add">
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
  },
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
  },
}
</script>
