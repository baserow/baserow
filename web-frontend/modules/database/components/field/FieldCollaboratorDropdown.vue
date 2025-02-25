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
      <div v-if="initialDisplayName">
        {{ initialDisplayName }}
      </div>
      <div v-else-if="hasValue()">
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
          @keyup="search"
        />
      </div>
      <ul
        ref="items"
        v-prevent-parent-scroll
        v-auto-overflow-scroll
        class="select__items"
        :class="{ 'select__items--no-max-height': fixedItemsImmutable }"
        tabindex="-1"
        @scroll="scroll"
      >
        <FieldCollaboratorDropdownItem
          v-if="showEmptyValue"
          :name="''"
          :value="null"
          :color="''"
        ></FieldCollaboratorDropdownItem>
        <FieldCollaboratorDropdownItem
          v-for="collaborator in results"
          :key="collaborator.id"
          :name="collaborator.name"
          :value="collaborator.id"
        ></FieldCollaboratorDropdownItem>
      </ul>
      <div v-if="isNotFound" class="select__description">
        {{ $t('fieldmultipleCollaboratorsDropdown.notFound') }}
      </div>
    </div>
  </div>
</template>

<script>
import inMemoryPaginatedDropdown from '@baserow/modules/core/mixins/inMemoryPaginatedDropdown'
import FieldCollaboratorDropdownItem from '@baserow/modules/database/components/field/FieldCollaboratorDropdownItem'

export default {
  name: 'FieldCollaboratorDropdown',
  components: { FieldCollaboratorDropdownItem },
  mixins: [inMemoryPaginatedDropdown],
  props: {
    collaborators: {
      type: Array,
      required: true,
    },
    showEmptyValue: {
      type: Boolean,
      required: false,
      default: true,
    },
    pageSize: {
      type: Number,
      required: false,
      default: 100, // override default pageSize of 20
    },
  },
  computed: {
    isNotFound() {
      return this.results.length === 0 && this.query !== ''
    },
  },
  watch: {
    collaborators() {
      this.fetch(1, this.query)
    },
  },
  methods: {
    filterItems(search) {
      return this.collaborators.filter((collaborator) => {
        return collaborator.name.toLowerCase().includes(search.toLowerCase())
      })
    },
  },
}
</script>
