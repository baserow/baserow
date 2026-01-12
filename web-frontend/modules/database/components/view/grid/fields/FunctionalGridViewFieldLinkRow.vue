<template>
  <div class="grid-view__cell grid-field-many-to-many__cell">
    <div class="grid-field-many-to-many__list">
      <div
        v-for="item in value"
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
            $t('functionnalGridViewFieldLinkRow.unnamed', {
              value: item.id,
            })
          }}
        </span>
      </div>
      <div v-if="shouldFetchRow" class="grid-field-many-to-many__item">...</div>
    </div>
  </div>
</template>

<script>
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  name: 'FunctionalGridViewFieldLinkRow',
  props: {
    value: {
      type: Array,
      default: () => [],
    },
    row: {
      type: Object,
      required: true,
    },
  },
  computed: {
    shouldFetchRow() {
      return (
        this.value?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !this.row._?.fullyLoaded
      )
    },
  },
}
</script>
