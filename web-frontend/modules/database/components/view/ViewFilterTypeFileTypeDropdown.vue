<template>
  <Dropdown
    :value="filter.value"
    :show-search="false"
    :fixed-items="true"
    class="filters__value-dropdown"
    @input="$emit('input', $event)"
  >
    <DropdownItem
      :name="$t('viewFilterTypeFileTypeDropdown.image')"
      value="image"
    ></DropdownItem>
    <DropdownItem
      :name="$t('viewFilterTypeFileTypeDropdown.document')"
      value="document"
    ></DropdownItem>
  </Dropdown>
</template>

<script>
export default {
  name: 'ViewFilterTypeFileTypeDropdown',
  props: {
    filter: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
}
</script>
