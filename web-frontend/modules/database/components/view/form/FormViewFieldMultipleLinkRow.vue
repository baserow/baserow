<template>
  <div class="control__elements">
    <div
      v-for="(v, index) in value"
      :key="index + '-' + value[index].id"
      class="margin-bottom-2 flex"
    >
      <div class="flex-100">
        <PaginatedDropdown
          :fetch-page="fetchPage"
          :value="value[index].id"
          :initial-display-name="value[index].value"
          :error="touched && !valid && isInvalidValue(value[index])"
          :fetch-on-open="lazyLoad"
          :disabled="readOnly"
          :include-display-name-in-selected-event="true"
          @input="updateValue($event, index)"
        ></PaginatedDropdown>
      </div>
      <div class="align-right">
        <Button
          type="secondary"
          tag="a"
          icon="iconoir-bin"
          @click="remove(index)"
        ></Button>
      </div>
    </div>
    <div>
      <Button
        type="secondary"
        tag="a"
        icon="iconoir-plus"
        @click="add"
      ></Button>
    </div>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import ViewService from '@baserow/modules/database/services/view'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'FormViewFieldMultipleLinkRow',
  components: { PaginatedDropdown },
  mixins: [rowEditField],
  props: {
    slug: {
      type: String,
      required: true,
    },
    /**
     * In some cases, for example in the form view preview, we only want to fetch the
     * first related rows after the user has opened the dropdown. This will prevent a
     * race condition where the enabled state of the field might not yet been updated
     * before we fetch the related rows. If the state has not yet been changed in the
     * backend, it will result in an error.
     */
    lazyLoad: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  created() {
    if (this.value.length === 0 && this.required) {
      this.add()
    }
  },
  methods: {
    getValidationError(value) {
      const error = rowEditField.methods.getValidationError.call(this, value)

      if (!this.required && error === null) {
        const empty = value.some((v) => this.isInvalidValue(v))
        if (empty) {
          return this.$t('error.requiredField')
        }
      }

      return error
    },
    isInvalidValue(value) {
      return !Number.isInteger(value.id)
    },
    fetchPage(page, search) {
      const publicAuthToken =
        this.$store.getters['page/view/public/getAuthToken']
      return ViewService(this.$client).linkRowFieldLookup(
        this.slug,
        this.field.id,
        page,
        search,
        100,
        publicAuthToken
      )
    },
    add() {
      const newValue = clone(this.value)
      newValue.push({
        id: false,
        value: '',
      })
      this.$emit('update', newValue, this.value)
    },
    remove(index) {
      const newValue = clone(this.value)
      newValue.splice(index, 1)
      this.$emit('update', newValue, this.value)
    },
    updateValue({ value, displayName }, index) {
      const newValue = clone(this.value)
      newValue[index] = { id: value, value: displayName }
      this.$emit('update', newValue, this.value)
    },
  },
}
</script>
