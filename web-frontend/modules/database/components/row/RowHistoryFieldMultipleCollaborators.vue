<template>
  <div class="row-history-entry__field-content">
    <ul class="row-history-field-multiple-collaborators__items">
      <li
        v-for="item in allItems"
        :key="item.id"
        class="row-history-field-multiple-collaborators__item"
      >
        <div
          class="row-history-field-multiple-collaborators__name"
          :class="{
            'row-history-field-multiple-collaborators__item--removed':
              removedItems.includes(item),
            'row-history-field-multiple-collaborators__item--added':
              addedItems.includes(item),
          }"
        >
          {{ name(item) }}
        </div>
        <div class="row-history-field-multiple-collaborators__initials">
          {{ initials(name(item)) }}
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'RowHistoryFieldMultipleCollaborators',
  mixins: [collaboratorName],
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
            (item) => item.id === before.id
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
            (item) => item.id === after.id
          ) === -1
        )
      })
    },
  },
  methods: {
    name(item) {
      return this.getCollaboratorName(item, this.store)
    },
    initials(name) {
      return name.slice(0, 1).toUpperCase()
    },
  },
}
</script>
