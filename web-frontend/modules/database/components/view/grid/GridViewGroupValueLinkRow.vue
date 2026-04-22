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
          {{
            item.value || $t('gridViewFieldLinkRow.unnamed', { value: item.id })
          }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GridViewGroupValueLinkRow',
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
