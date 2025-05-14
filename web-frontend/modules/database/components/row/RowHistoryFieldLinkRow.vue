<template>
  <div class="row-history-entry__field-content">
    <div
      v-for="item in allItems"
      :key="item"
      :class="{
        'row-history-entry__diff--removed': removedItems.includes(item),
        'row-history-entry__diff--added': addedItems.includes(item),
      }"
      class="row-history-entry__diff"
    >
      {{ rowName(item) }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'RowHistoryFieldLinkRow',
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
      const itemsBefore = this.entry.before[this.fieldIdentifier]
      const itemsAfter = this.entry.after[this.fieldIdentifier] || []
      if (!itemsBefore) {
        return []
      }
      return itemsBefore.filter(
        (before) => itemsAfter.findIndex((item) => item === before) === -1
      )
    },
    addedItems() {
      const itemsBefore = this.entry.before[this.fieldIdentifier] || []
      const itemsAfter = this.entry.after[this.fieldIdentifier]
      if (!itemsAfter) {
        return []
      }
      return itemsAfter.filter(
        (after) => itemsBefore.findIndex((item) => item === after) === -1
      )
    },
  },
  methods: {
    rowName(id) {
      return this.entry.fields_metadata[this.fieldIdentifier].linked_rows[id]
        ?.value
    },
  },
}
</script>
