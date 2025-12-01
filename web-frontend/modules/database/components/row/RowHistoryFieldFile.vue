<template>
  <div class="row-history-entry__field-content">
    <div
      v-for="item in allItems"
      :key="item.id"
      :class="{
        'row-history-entry__diff--removed': removedItems.includes(item),
        'row-history-entry__diff--added': addedItems.includes(item),
      }"
      class="row-history-entry__diff"
    >
      {{ item.visible_name }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'RowHistoryFieldFile',
  props: {
    entry: {
      type: Object,
      required: true,
    },
    fieldIdentifier: {
      type: String,
      required: true,
    },
    field: {
      type: Object,
      required: false,
      default: null,
    },
  },
  computed: {
    allItems() {
      return this.removedItems.concat(this.addedItems)
    },
    removedItems() {
      if (!this.entry.before[this.fieldIdentifier]) {
        return []
      }
      return this.entry.before[this.fieldIdentifier].filter((before) => {
        return (
          (this.entry.after[this.fieldIdentifier] || []).findIndex(
            (item) => item.name === before.name
          ) === -1
        )
      })
    },
    addedItems() {
      if (!this.entry.after[this.fieldIdentifier]) {
        return []
      }
      return this.entry.after[this.fieldIdentifier].filter((after) => {
        return (
          (this.entry.before[this.fieldIdentifier] || []).findIndex(
            (item) => item.name === after.name
          ) === -1
        )
      })
    },
  },
}
</script>
