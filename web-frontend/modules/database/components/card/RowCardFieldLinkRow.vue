<template functional>
  <div class="card-many-to-many__list-wrapper">
    <div class="card-many-to-many__list">
      <div
        v-for="item in props.value"
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
      <div
        v-if="$options.methods.shouldFetchRow(props)"
        class="card-many-to-many__item card-link-row"
        :class="{
          'card-many-to-many__item--loading':
            $options.methods.isFetchingRow(props),
        }"
      >
        <div v-if="$options.methods.isFetchingRow(props)" class="loading"></div>
        <span v-else>...</span>
      </div>
    </div>
  </div>
</template>

<script>
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  height: 22,
  methods: {
    shouldFetchRow(props) {
      return (
        props.value?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !props.row._?.fullyLoaded
      )
    },
    isFetchingRow(props) {
      return props.row._?.fetching
    },
  },
}
</script>
