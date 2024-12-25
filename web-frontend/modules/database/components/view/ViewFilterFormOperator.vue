<template>
  <div class="filters__operator">
    <span v-if="index === 0" class="filters__operator-where">{{
      $t('viewFilterContext.where')
    }}</span>
    <Dropdown
      v-if="index === 1 && !disableFilter"
      :value="filterType"
      :show-search="false"
      :fixed-items="true"
      @input="$emit('updateFilterType', $event)"
    >
      <DropdownItem
        :name="$t('viewFilterContext.and')"
        value="AND"
      ></DropdownItem>
      <DropdownItem
        :name="$t('viewFilterContext.or')"
        value="OR"
      ></DropdownItem>
    </Dropdown>
    <span
      v-if="index > 1 || (index > 0 && disableFilter)"
      class="filters__operator-text"
    >
      {{
        filterType === 'AND'
          ? $t('viewFilterContext.and')
          : $t('viewFilterContext.or')
      }}
    </span>
  </div>
</template>

<script>
export default {
  name: 'ViewFilterFormOperator',
  props: {
    index: {
      type: Number,
      required: true,
    },
    filterType: {
      type: String,
      required: true,
    },
    disableFilter: {
      type: Boolean,
      required: true,
    },
  },
}
</script>
