<template>
  <div
    class="ab-dropdown"
    :class="{
      'ab-dropdown--floating': !showInput,
      'ab-dropdown--disabled': disabled,
    }"
    :tabindex="realTabindex"
    @focusin="show()"
    @focusout="focusout($event)"
  >
    <a v-if="showInput" class="ab-dropdown__selected" @click="show()">
      <template v-if="hasValue()">
        <slot name="value">
          <template v-if="multiple">
            <span class="ab-dropdown__selected-text">{{
              selectedName.join(', ')
            }}</span>
          </template>
          <template v-else>
            <i
              v-if="selectedIcon"
              class="ab-dropdown__selected-icon"
              :class="selectedIcon"
            />
            <img
              v-if="selectedImage"
              class="ab-dropdown__selected-image"
              :src="selectedImage"
            />
            <span class="ab-dropdown__selected-text">{{ selectedName }}</span>
          </template>
        </slot>
      </template>
      <template v-else>
        <slot name="defaultValue">
          <span class="ab-dropdown__selected-placeholder">{{
            placeholder ? placeholder : $t('action.makeChoice')
          }}</span>
        </slot>
      </template>
      <i class="ab-dropdown__toggle-icon iconoir-nav-arrow-down"></i>
    </a>
    <div
      ref="itemsContainer"
      class="ab-dropdown__items"
      :class="{
        hidden: !open,
        'ab-dropdown__items--fixed': fixedItemsImmutable,
        'ab-dropdown__items--max-width': maxWidth,
      }"
    >
      <div v-if="showSearch" class="select__search">
        <i class="select__search-icon iconoir-search"></i>
        <input
          ref="search"
          v-model="query"
          type="text"
          class="select__search-input"
          :placeholder="searchText === null ? $t('action.search') : searchText"
          tabindex="0"
          @keyup="emitSearch ? $emit('query-change', query) : search(query)"
        />
      </div>
      <ul
        v-show="hasDropdownItem"
        ref="items"
        v-auto-overflow-scroll
        class="select__items"
        :class="{ 'select__items--no-max-height': fixedItemsImmutable }"
        tabindex="-1"
        @scroll="$emit('scroll', $event)"
      >
        <slot></slot>
      </ul>
      <div v-if="!hasDropdownItem" class="select__items--empty">
        <slot name="emptyState">
          {{ $t('dropdown.empty') }}
        </slot>
      </div>
      <div v-if="showFooter" class="select__footer">
        <slot name="footer"></slot>
      </div>
    </div>
  </div>
</template>

<script>
import dropdown from '@baserow/modules/core/mixins/dropdown'

export default {
  name: 'ABDropdown',
  mixins: [dropdown],
  props: {
    /**
     * When `emitSearch` is set to `true`, this will emit the search
     * query instead of performing local, per dropdown-item, search.
     */
    emitSearch: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
