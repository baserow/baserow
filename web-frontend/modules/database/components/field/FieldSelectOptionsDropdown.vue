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
    @contextmenu.stop
    @focusin="show()"
    @focusout="focusout($event)"
  >
    <a
      v-if="showInput"
      class="select-options__dropdown-selected dropdown__selected"
      @click="show()"
    >
      <div
        v-if="multiple && hasValue()"
        class="select-options__multiple-dropdown-options"
      >
        <div
          v-for="(name, index) in selectedName"
          :key="index"
          class="select-options__dropdown-option"
          :class="'background-color--' + selectedColor[index]"
        >
          {{ name }}
        </div>
      </div>
      <div
        v-else-if="hasValue()"
        class="select-options__dropdown-option"
        :class="'background-color--' + selectedColor"
      >
        {{ selectedName }}
      </div>
      <i
        v-if="!disabled"
        class="dropdown__toggle-icon iconoir-nav-arrow-down"
      ></i>
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
          :placeholder="searchText"
          tabindex="0"
          @keyup="search(query)"
          @keydown.enter="createOptionViaSearch($event, query)"
        />
      </div>
      <ul
        ref="items"
        v-prevent-parent-scroll
        v-auto-overflow-scroll
        class="select__items"
        :class="{ 'select__items--no-max-height': fixedItemsImmutable }"
        tabindex="-1"
      >
        <FieldSelectOptionsDropdownItem
          v-if="showEmptyValue"
          :name="''"
          :value="null"
          :color="''"
        ></FieldSelectOptionsDropdownItem>
        <FieldSelectOptionsDropdownItem
          v-for="option in options"
          :key="option.id"
          :name="option.value"
          :value="option.id"
          :color="option.color"
        ></FieldSelectOptionsDropdownItem>
      </ul>
      <template v-if="canCreateOption">
        <div class="select__description">
          {{ $t('fieldSingleSelectDropdown.notFound') }}
        </div>
        <div class="select__footer">
          <a
            class="select__footer-button"
            :class="{ 'button--loading': createOptionLoading }"
            @click="createOption(query)"
          >
            <i class="iconoir-plus"></i>
            {{ $t('action.create') }} {{ query }}
          </a>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import dropdown from '@baserow/modules/core/mixins/dropdown'
import FieldSelectOptionsDropdownItem from '@baserow/modules/database/components/field/FieldSelectOptionsDropdownItem'

export default {
  name: 'FieldSelectOptionsDropdown',
  components: { FieldSelectOptionsDropdownItem },
  mixins: [dropdown],
  props: {
    options: {
      type: Array,
      required: true,
    },
    allowCreateOption: {
      type: Boolean,
      required: false,
      default: false,
    },
    showEmptyValue: {
      type: Boolean,
      required: false,
      default: true,
    },
    size: {
      type: String,
      required: false,
      default: 'regular',
    },
  },
  data() {
    return {
      createOptionLoading: false,
    }
  },
  computed: {
    canCreateOption() {
      return this.allowCreateOption && this.query !== '' && !this.hasItems
    },
    selectedColor() {
      return this.getSelectedProperty(this.value, 'color')
    },
  },
  methods: {
    forceRefreshSelectedValue() {
      this._computedWatchers.selectedColor.run()
      dropdown.methods.forceRefreshSelectedValue.call(this)
    },
    createOption(value) {
      if (this.createOptionLoading) {
        return
      }

      this.createOptionLoading = true
      const done = (success) => {
        this.createOptionLoading = false

        // If the option was created successfully whe have to find that option, select
        // it and hide the dropdown.
        if (success) {
          const option = this.options.find((o) => o.value === value)
          if (option !== undefined) {
            this.select(option.id)
          }
        }
      }
      this.$emit('create-option', { value, done })
    },
    createOptionViaSearch(event, query) {
      if (this.canCreateOption) {
        event.stopPropagation()
        this.createOption(query)
      }
    },
  },
}
</script>
