<template>
  <div
    class="dropdown"
    :class="{
      'dropdown--floating': !showInput,
      'dropdown--disabled': disabled,
      'dropdown--large': size === 'large',
      'dropdown--error': error,
    }"
    :tabindex="realTabindex"
    @focusin="show()"
    @focusout="focusout($event)"
  >
    <a v-if="showInput" class="dropdown__selected" @click="show()">
      <template v-if="displayName !== null">
        <span class="dropdown__selected-text">{{ displayName }}</span>
      </template>
      <template v-else>{{
        notSelectedText === null ? $t('action.makeChoice') : notSelectedText
      }}</template>
      <i class="dropdown__toggle-icon iconoir-nav-arrow-down"></i>
    </a>
    <div
      ref="itemsContainer"
      class="dropdown__items"
      :class="{
        hidden: !open,
        'dropdown__items--fixed': fixedItemsImmutable,
      }"
    >
      <div v-if="showSearch" class="select__search">
        <i class="select__search-icon iconoir-search"></i>
        <input
          ref="search"
          v-model="query"
          type="text"
          class="select__search-input"
          tabindex="0"
          :placeholder="searchText === null ? $t('action.search') : searchText"
          @input="search"
        />
      </div>
      <ul
        ref="items"
        v-auto-overflow-scroll
        class="select__items"
        :class="{ 'select__items--no-max-height': fixedItemsImmutable }"
        tabindex="-1"
        @scroll="scroll"
      >
        <DropdownItem
          v-if="addEmptyItem"
          :name="emptyItemDisplayName"
          :value="null"
        ></DropdownItem>
        <DropdownItem
          v-for="result in results"
          :key="result[idName]"
          :name="result[valueName]"
          :value="result[idName]"
        ></DropdownItem>
        <div v-if="loading" class="select__items-loading"></div>
      </ul>
    </div>
  </div>
</template>

<script>
import paginatedDropdown from '@baserow/modules/core/mixins/paginatedDropdown'

export default {
  name: 'PaginatedDropdown',
  mixins: [paginatedDropdown],
  props: {
    fetchPage: {
      type: Function,
      required: true,
    },
    includeDisplayNameInSelectedEvent: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
