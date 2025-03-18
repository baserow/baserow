<template>
  <Context ref="context" class="sortings" max-height-if-outside-viewport>
    <div class="sortings__content">
      <div
        v-if="view.sortings.length === 0"
        v-auto-overflow-scroll
        class="sortings__none sortings__none--scrollable"
      >
        <div class="sortings__none-title">
          {{ $t('viewSortContext.noSortTitle') }}
        </div>
        <div class="sortings__none-description">
          {{ $t('viewSortContext.noSortText') }}
        </div>
      </div>
      <div
        v-if="view.sortings.length > 0"
        v-auto-overflow-scroll
        class="sortings__items sortings__items--scrollable"
      >
        <div
          v-for="(sort, index) in view.sortings"
          :key="sort.id"
          class="sortings__item"
          :class="{
            'sortings__item--loading': sort._.loading,
          }"
          :set="(field = getField(sort.field))"
        >
          <a
            v-if="!disableSort"
            class="sortings__remove"
            @click="deleteSort(sort)"
          >
            <i class="iconoir-cancel"></i>
          </a>

          <div class="sortings__description">
            <template v-if="index === 0"
              >{{ $t('viewSortContext.sortBy') }}
            </template>
            <template v-if="index > 0"
              >{{ $t('viewSortContext.thenBy') }}
            </template>
          </div>
          <div class="sortings__field">
            <Dropdown
              :value="sort.field"
              :disabled="disableSort"
              :fixed-items="true"
              class="dropdown--floating"
              @input="updateSort(sort, { field: $event })"
            >
              <DropdownItem
                v-for="field in fields"
                :key="'sort-field-' + sort.id + '-' + field.id"
                :name="field.name"
                :value="field.id"
                :disabled="sort.field !== field.id && !isFieldAvailable(field)"
              ></DropdownItem>
            </Dropdown>
          </div>
          <ViewSortOrder
            :disabled="disableSort"
            :sort-types="getSortTypes(field)"
            :type="sort.type"
            :order="sort.order"
            @update-order="
              updateSort(sort, { order: $event.order, type: $event.type })
            "
          ></ViewSortOrder>
        </div>
      </div>
      <div
        v-if="view.sortings.length < availableFieldsLength && !disableSort"
        class="context__footer"
      >
        <ButtonText
          ref="addDropdownToggle"
          icon="iconoir-plus"
          @click="$refs.addDropdown.toggle($refs.addDropdownToggle.$el)"
        >
          {{ $t('viewSortContext.addSort') }}
        </ButtonText>
        <div class="sortings__add">
          <Dropdown
            ref="addDropdown"
            :show-input="false"
            :fixed-items="true"
            @input="addSort"
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
import ViewSortOrder from '@baserow/modules/database/components/view/ViewSortOrder'
import { DEFAULT_SORT_TYPE_KEY } from '@baserow/modules/database/constants'

export default {
  name: 'ViewSortContext',
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
    disableSort: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    availableFieldsLength() {
      return this.fields.filter(this.getCanSortInView).length
    },
    availableFields() {
      return this.fields.filter((f) => this.isFieldAvailable(f))
    },
  },
  methods: {
    getFieldType(field) {
      return this.$registry.get('field', field.type)
    },
    getCanSortInView(field) {
      return this.getFieldType(field).getCanSortInView(field)
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
      const allFieldIds = this.view.sortings.map((sort) => sort.field)
      return this.getCanSortInView(field) && !allFieldIds.includes(field.id)
    },
    async addSort(fieldId) {
      this.$refs.addDropdown.hide()

      try {
        await this.$store.dispatch('view/createSort', {
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
    async deleteSort(sort) {
      try {
        await this.$store.dispatch('view/deleteSort', {
          view: this.view,
          sort,
          readOnly: this.readOnly,
        })
        this.$emit('changed')
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateSort(sort, values) {
      if (this.disableSort) {
        return
      }

      // If the field has changed, the type might not be compatible anymore. If so,
      // then we're falling back on the default sort type.
      if (values.field) {
        const sortType = values.type || sort.type
        const field = this.getField(values.field)
        const fieldType = this.getFieldType(field)
        const sortTypes = fieldType.getSortTypes(field)
        if (!Object.prototype.hasOwnProperty.call(sortTypes, sortType)) {
          values.type = DEFAULT_SORT_TYPE_KEY
        }
      }

      try {
        await this.$store.dispatch('view/updateSort', {
          sort,
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
