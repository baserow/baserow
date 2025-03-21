<template>
  <Context
    ref="context"
    :overflow-scroll="true"
    :max-height-if-outside-viewport="true"
  >
    <ul class="context__menu">
      <li
        v-for="value in hiddenRecords"
        :key="'hidden-record' + value.id"
        class="expand-on-overflow-hidden-context__dropdown-item"
      >
        {{ value[nameKey] }}
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'ExpandOnOverflowHiddenContext',
  mixins: [context],
  props: {
    nameKey: {
      required: false,
      type: String,
      default: 'name',
    },
    hiddenRecords: {
      required: true,
      type: Array,
    },
  },
}
</script>
