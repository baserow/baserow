<template>
  <div class="card-many-to-many__list-wrapper">
    <div class="card-many-to-many__list">
      <div
        v-for="item in value"
        :key="item.id"
        class="card-many-to-many__item card-link-row"
        :class="{
          'card-link-row--unnamed': item.value === null || item.value === '',
        }"
      >
        <span class="card-many-to-many__name">
          {{ item.value || 'unnamed row ' + item.id }}
        </span>
      </div>
      <div v-if="isTruncated" class="card-many-to-many__item card-link-row">
        <span>...</span>
      </div>
    </div>
  </div>
</template>

<script>
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  name: 'GroupByFieldLinkRow',
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    isTruncated() {
      return this.value?.length >= LINKED_ITEMS_DEFAULT_LOAD_COUNT
    },
  },
}
</script>
