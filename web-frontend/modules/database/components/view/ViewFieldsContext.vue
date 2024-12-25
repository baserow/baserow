<template>
  <Context
    ref="context"
    class="hidings"
    max-height-if-outside-viewport
    @shown="shown()"
  >
    <div class="hidings__head">
      <FormGroup
        v-if="allowCoverImageField"
        small-label
        :label="$t('viewFieldsContext.coverField')"
        required
        class="hidings__cover margin-bottom-2"
      >
        <Dropdown
          :value="coverImageField"
          :disabled="
            !$hasPermission(
              'database.table.view.update',
              view,
              database.workspace.id
            )
          "
          @input="
            coverImageField !== $event &&
              $emit('update-cover-image-field', $event)
          "
        >
          <DropdownItem
            :name="$t('viewFieldsContext.noCover')"
            :value="null"
          ></DropdownItem>
          <DropdownItem
            v-for="fileField in fileFields"
            :key="fileField.id"
            :icon="fileField._.type.iconClass"
            :name="fileField.name"
            :value="fileField.id"
          ></DropdownItem>
        </Dropdown>
      </FormGroup>

      <div class="hidings__search">
        <i class="hidings__search-icon iconoir-search"></i>
        <input
          ref="search"
          v-model="query"
          type="text"
          :placeholder="$t('viewFieldsContext.search')"
          class="hidings__search-input"
        />
      </div>
    </div>
    <div v-auto-overflow-scroll class="hidings__body">
      <ul class="hidings__list margin-top-1 margin-bottom-0">
        <li
          v-for="field in filteredFields"
          :key="field.id"
          v-sortable="{
            id: field.id,
            update: order,
            handle: '[data-field-handle]',
          }"
          class="hidings__item"
        >
          <a class="hidings__item-handle" data-field-handle></a>
          <SwitchInput
            v-if="allowHidingFields"
            small
            :value="!isHidden(field.id)"
            @input="updateFieldOptionsOfField(field, { hidden: !$event })"
          >
            <i class="switch__icon" :class="field._.type.iconClass"></i>
            <span>{{ field.name }}</span>
          </SwitchInput>
          <div v-else class="hidings__item-name">
            <i class="switch__icon" :class="field._.type.iconClass"></i>
            <span>{{ field.name }}</span>
          </div>
        </li>
      </ul>
    </div>
    <div v-if="allowHidingFields" v-show="query === ''" class="hidings__footer">
      <Button
        type="secondary"
        class="hidings__footer-button"
        @click="!noneSelected && updateAllFieldOptions({ hidden: true })"
      >
        {{ $t('viewFieldsContext.hideAll') }}
      </Button>
      <Button
        type="secondary"
        @click="!allSelected && updateAllFieldOptions({ hidden: false })"
      >
        {{ $t('viewFieldsContext.showAll') }}
      </Button>
    </div>
  </Context>
</template>

<script>
import { mapGetters } from 'vuex'
import { escapeRegExp } from '@baserow/modules/core/utils/string'
import context from '@baserow/modules/core/mixins/context'
import { clone } from '@baserow/modules/core/utils/object'
import { sortFieldsByOrderAndIdFunction } from '@baserow/modules/database/utils/view'

export default {
  name: 'ViewFieldsContext',
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
    fieldOptions: {
      type: Object,
      required: true,
    },
    coverImageField: {
      required: false,
      default: null,
      validator: (prop) => typeof prop === 'number' || prop === null,
    },
    allowCoverImageField: {
      type: Boolean,
      required: false,
      default: false,
    },
    allowHidingFields: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  data() {
    return {
      query: '',
    }
  },
  computed: {
    noneSelected() {
      for (const i in this.fields) {
        if (!this.isHidden(this.fields[i].id)) {
          return false
        }
      }
      return true
    },
    allSelected() {
      for (const i in this.fields) {
        if (this.isHidden(this.fields[i].id)) {
          return false
        }
      }
      return true
    },
    filteredFields() {
      const query = this.query

      return this.fields
        .filter((field) => {
          const regex = new RegExp('(' + escapeRegExp(query) + ')', 'i')
          return field.name.match(regex)
        })
        .sort(sortFieldsByOrderAndIdFunction(this.fieldOptions))
    },
    fileFields() {
      return this.fields.filter((field) => {
        const fieldType = this.$registry.get('field', field.type)
        return fieldType.canRepresentFiles(field)
      })
    },
    ...mapGetters({
      allFields: 'field/getAll',
    }),
  },
  methods: {
    order(order, oldOrder) {
      this.$emit('update-order', {
        order: [this.allFields[0].id, ...order], // Add primary field first
        oldOrder,
      })
    },
    updateAllFieldOptions(values) {
      const newFieldOptions = {}
      const oldFieldOptions = clone(this.fieldOptions)
      this.fields.forEach((field) => {
        newFieldOptions[field.id] = values
      })

      this.$emit('update-all-field-options', {
        newFieldOptions,
        oldFieldOptions,
      })
    },
    updateFieldOptionsOfField(field, values) {
      this.$emit('update-field-options-of-field', {
        field,
        values,
        oldValues: { hidden: this.fieldOptions[field.id].hidden },
      })
    },
    isHidden(fieldId) {
      const exists = Object.prototype.hasOwnProperty.call(
        this.fieldOptions,
        fieldId
      )
      return exists ? this.fieldOptions[fieldId].hidden : false
    },
    shown() {
      this.query = ''
      this.$nextTick(() => {
        this.$refs.search.focus()
      })
    },
  },
}
</script>
