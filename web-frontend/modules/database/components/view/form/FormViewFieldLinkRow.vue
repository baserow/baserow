<template>
  <div class="control__elements">
    <PaginatedDropdown
      :fetch-page="fetchPage"
      :value="dropdownValue"
      :initial-display-name="initialDisplayName"
      :error="touched && !valid"
      :fetch-on-open="lazyLoad"
      :disabled="readOnly"
      :include-display-name-in-selected-event="true"
      @input="updateValue($event)"
      @hide="touch()"
    ></PaginatedDropdown>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import ViewService from '@baserow/modules/database/services/view'

export default {
  name: 'FormViewFieldLinkRow',
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
  computed: {
    dropdownValue() {
      return this.value.length === 0 ? false : this.value[0].id
    },
    initialDisplayName() {
      return this.value.length === 0 ? '' : this.value[0].value
    },
  },
  methods: {
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
    updateValue({ value, displayName }) {
      const selection =
        value === null || value === ''
          ? []
          : [{ id: value, value: displayName }]
      this.$emit('update', selection, this.value)
    },
  },
}
</script>
