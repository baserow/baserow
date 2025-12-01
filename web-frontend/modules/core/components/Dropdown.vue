<template>
  <div
    :id="forInput"
    class="dropdown"
    :class="{
      'dropdown--floating': !showInput,
      'dropdown--disabled': disabled,
      'dropdown--large': size === 'large',
      'dropdown--error': error,
    }"
    :tabindex="realTabindex"
    role="list"
    @focusin="show()"
    @focusout="focusout($event)"
  >
    <a v-if="showInput" class="dropdown__selected" @click="show()">
      <template v-if="hasValue()">
        <slot name="selectedValue">
          <template v-if="multiple">
            <span
              class="dropdown__selected-text"
              :title="selectedName.join(', ')"
              >{{ selectedName.join(', ') }}</span
            >
          </template>
          <template v-else>
            <i
              v-if="selectedIcon"
              class="dropdown__selected-icon"
              :class="selectedIcon"
            />
            <img
              v-if="selectedImage"
              class="dropdown__selected-image"
              :src="selectedImage"
            />
            <span class="dropdown__selected-text" :title="selectedName">{{
              selectedName
            }}</span>
          </template>
        </slot>
      </template>
      <template v-else>
        <slot name="defaultValue">
          <span class="dropdown__selected-placeholder">{{
            placeholder ? placeholder : $t('action.makeChoice')
          }}</span>
        </slot>
      </template>

      <i class="dropdown__toggle-icon iconoir-nav-arrow-down"></i>
    </a>
    <div
      ref="itemsContainer"
      class="dropdown__items"
      :class="{
        hidden: !open && !openOnMount,
        'dropdown__items--fixed': fixedItemsImmutable,
        'dropdown__items--max-width': maxWidth,
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
          @keyup="search(query)"
        />
      </div>
      <ul
        v-show="hasItems && hasDropdownItem"
        ref="items"
        v-auto-overflow-scroll
        class="select__items"
        :class="{ 'select__items--no-max-height': fixedItemsImmutable }"
        tabindex="-1"
      >
        <slot></slot>
      </ul>
      <div v-if="!hasItems || !hasDropdownItem" class="select__items--empty">
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
  name: 'Dropdown',
  mixins: [dropdown],
}
</script>
