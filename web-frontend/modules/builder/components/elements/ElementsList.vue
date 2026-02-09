<template>
  <ul class="elements-list">
    <ElementsListItem
      v-for="element in filteredElements"
      :key="element.id"
      :element="element"
      :filtered-search-elements="filteredSearchElements"
      @select="$emit('select', $event)"
    >
      <template #children="{ children }">
        <ElementsList
          v-if="children.length"
          name="nested-elements-list"
          :elements="children"
          :filtered-search-elements="filteredSearchElements"
          @select="$emit('select', $event)"
        />
      </template>
    </ElementsListItem>
  </ul>
</template>

<script>
import ElementsListItem from '@baserow/modules/builder/components/elements/ElementsListItem'

export default {
  name: 'ElementsList',
  components: { ElementsListItem },
  props: {
    elements: {
      type: Array,
      required: true,
    },
    filteredSearchElements: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: ['select'],
  computed: {
    /**
     * Responsible for returning elements to display in `ElementsListItem`.
     * If we've been given an array of `filteredSearchElements`, we'll filter
     * the elements to only include those that match the `id` of the element.
     * If `filteredSearchElements` is empty, then we show all `elements`.
     */
    filteredElements() {
      if (this.filteredSearchElements.length === 0) {
        return this.elements
      } else {
        return this.elements.filter((element) => {
          return this.filteredSearchElements.includes(element.id)
        })
      }
    },
  },
}
</script>
