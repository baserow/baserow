<template>
  <ul class="list">
    <li v-for="(item, index) in items" :key="index" class="list__item">
      <div class="list__left-side">
        <Checkbox
          v-if="selectable"
          :checked="selectedItemsIds.includes(item.id)"
          @input="selected($event, item, index)"
        />
        <slot name="left-side" :item="item"></slot>
      </div>
      <div v-for="attribute in attributesValidated" :key="attribute">
        {{ item[attribute] }}
      </div>

      <div v-if="hasRightSlot" class="list__right-side">
        <slot name="right-side" :item="item"></slot>
      </div>
    </li>
  </ul>
</template>

<script>
export default {
  name: 'List',
  props: {
    items: {
      type: Array,
      required: false,
      default: () => [],
    },
    selectedItems: {
      type: Array,
      required: false,
      default: () => [],
    },
    attributes: {
      type: Array,
      required: false,
      default: () => null,
    },
    selectable: {
      type: Boolean,
      required: false,
      default: () => false,
    },
  },
  emits: ['selected'],
  computed: {
    /**
     * If no attributes are provided as a prop we will just use all the attributes
     * of the first item
     */
    attributesValidated() {
      if (this.items.length) {
        return this.attributes ?? Object.keys(this.items[0])
      }
      return []
    },
    selectedItemsIds() {
      return this.selectedItems.map((item) => item.id)
    },
    hasRightSlot() {
      return !!(this.$slots && this.$slots['right-side'])
    },
  },
  methods: {
    selected(value, item, index) {
      if (value) {
        this.selectedItemsIds.push(item.id)
      } else {
        this.selectedItemsIds.splice(this.selectedItemsIds.indexOf(item.id), 1)
      }
      this.$emit('selected', { value, item, index })
    },
  },
}
</script>
