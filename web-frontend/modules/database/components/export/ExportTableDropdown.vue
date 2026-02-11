<template>
  <Dropdown
    v-model="localValue"
    :show-search="true"
    :disabled="loading"
    @input="$emit('input', $event)"
  >
    <DropdownItem
      :name="$t('exportTableDropdown.exportEntireTable')"
      :value="null"
    ></DropdownItem>

    <DropdownItem
      v-for="v in views"
      :key="v.id"
      :name="v.name"
      :value="v.id"
      :icon="v._.type.iconClass"
    >
    </DropdownItem>
  </Dropdown>
</template>

<script>
import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'

export default {
  name: 'ExportTableDropdown',
  components: { Dropdown, DropdownItem },
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
    views: {
      type: Array,
      required: true,
    },
    value: {
      type: Number,
      required: false,
      default: null,
    },
  },
  emits: ['input'],
  data() {
    return {
      localValue: this.value,
    }
  },
}
</script>
