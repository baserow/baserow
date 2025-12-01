<template functional>
  <div class="grid-view__cell grid-field-many-to-many__cell">
    <div class="grid-field-many-to-many__list">
      <div
        v-for="item in props.value"
        :key="item.id"
        class="grid-field-many-to-many__item"
      >
        <span
          class="grid-field-many-to-many__name"
          :class="{
            'grid-field-link-row__unnamed':
              item.value === null || item.value === '',
          }"
          :title="item.value"
        >
          {{
            item.value ||
            parent.$t('functionnalGridViewFieldLinkRow.unnamed', {
              value: item.id,
            })
          }}
        </span>
      </div>
      <div
        v-if="$options.methods.shouldFetchRow(props)"
        class="grid-field-many-to-many__item"
      >
        ...
      </div>
    </div>
  </div>
</template>

<script>
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  name: 'FunctionalGridViewFieldLinkRow',
  methods: {
    shouldFetchRow(props) {
      return (
        props.value?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !props.row._?.fullyLoaded
      )
    },
  },
}
</script>
