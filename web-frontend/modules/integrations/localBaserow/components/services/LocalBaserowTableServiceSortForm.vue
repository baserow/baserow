<template>
  <div v-if="value">
    <div v-if="value.length === 0" class="sortings__none">
      <div class="sortings__none-title">
        {{ $t('localBaserowTableServiceSortForm.noSortTitle') }}
      </div>
      <div class="sortings__none-description">
        {{ $t('localBaserowTableServiceSortForm.noSortText') }}
      </div>
    </div>
    <div v-if="value.length > 0" v-auto-overflow-scroll class="sortings__items">
      <div
        v-for="(sort, index) in value"
        :key="sort.id"
        class="sortings__item"
        :set="(field = getField(sort.field))"
      >
        <a
          v-if="!disableSort"
          class="sortings__remove"
          @click.stop="deleteSort(sort)"
        >
          <i class="iconoir-cancel"></i>
        </a>

        <div v-if="sortMisconfigured(sort)">
          <div class="flex-grow-1">
            <p class="sortings__misconfigured-text">
              {{ $t('localBaserowTableServiceSortForm.sortMisconfigured') }}
            </p>
          </div>
        </div>

        <template v-else>
          <div class="sortings__description">
            <template v-if="index === 0">{{
              $t('localBaserowTableServiceSortForm.sortBy')
            }}</template>
            <template v-if="index > 0">{{
              $t('localBaserowTableServiceSortForm.thenBy')
            }}</template>
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
          <div
            class="sortings__order"
            :class="{ 'sortings__order--disabled': disableSort }"
          >
            <a
              class="sortings__order-item"
              :class="{ active: sort.order_by === 'ASC' }"
              @click="updateSort(sort, { order_by: 'ASC' })"
            >
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
            <a
              class="sortings__order-item"
              :class="{ active: sort.order_by === 'DESC' }"
              @click="updateSort(sort, { order_by: 'DESC' })"
            >
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
          </div>
        </template>
      </div>
    </div>
    <template v-if="value.length < availableFieldsLength && !disableSort">
      <div ref="addContextToggle">
        <ButtonText
          type="secondary"
          size="small"
          icon="iconoir-plus"
          @click="
            $refs.addContext.toggle($refs.addContextToggle, 'bottom', 'left', 2)
          "
        >
          {{ $t('localBaserowTableServiceSortForm.addSort') }}
        </ButtonText>
      </div>
      <Context
        ref="addContext"
        class="sortings__add-context"
        overflow-scroll
        max-height-if-outside-viewport
      >
        <ul ref="items" class="context__menu">
          <li
            v-for="field in fields"
            v-show="isFieldAvailable(field)"
            :key="field.id"
            class="context__menu-item"
          >
            <a class="context__menu-item-link" @click="addSort(field)">
              <i
                class="context__menu-icon"
                :class="getFieldType(field).iconClass"
              ></i>
              {{ field.name }}
            </a>
          </li>
        </ul>
      </Context>
    </template>
  </div>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'LocalBaserowTableServiceSortForm',
  mixins: [context],
  props: {
    value: {
      type: Array,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    disableSort: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    /**
     * Calculates the total amount of available fields.
     */
    availableFieldsLength() {
      return this.fields.filter(this.getCanSortInView).length
    },
  },
  methods: {
    /**
     * If a sort points to a `field` which is not present in `this.fields`,
     * or the field object is found, and the field is trashed, flag this sort
     * as being misconfigured. This is very unlikely to happen in the database,
     * but when this component is used in the builder, it is possible. In that
     * implementation, the builder needs the ability to display a misconfigured
     * sort so that the page designer can delete it.
     * @returns {Boolean} True if the filter is misconfigured, false otherwise.
     */
    sortMisconfigured(sort) {
      const field = this.getField(sort.field)
      return field === undefined || field.trashed
    },
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
      const allFieldIds = this.value.map((sort) => sort.field)
      return this.getCanSortInView(field) && !allFieldIds.includes(field.id)
    },
    addSort(field) {
      this.$refs.addContext.hide()
      const newSortings = [...this.value]
      newSortings.push({
        field: field.id,
        order_by: 'ASC',
      })
      this.$emit('input', newSortings)
    },
    deleteSort(sort) {
      const newSortings = this.value.filter(({ field }) => {
        return field !== sort.field
      })
      this.$emit('input', newSortings)
    },
    updateSort(sort, values) {
      const newSortings = this.value.map((sortConf) => {
        if (sortConf.field === sort.field) {
          return { ...sortConf, ...values }
        }
        return sortConf
      })
      this.$emit('input', newSortings)
    },
    getSortIndicator(field, index) {
      return this.getFieldType(field).getSortIndicator(field)[index]
    },
  },
}
</script>
