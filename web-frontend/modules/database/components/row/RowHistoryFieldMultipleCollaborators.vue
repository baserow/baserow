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
import _ from 'lodash'

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
      const itemsBefore = this.entry.before[this.fieldIdentifier]
      const itemsAfter = this.entry.after[this.fieldIdentifier] || []
      if (!itemsBefore) {
        return []
      }
      return itemsBefore.filter(
        (before) =>
          itemsAfter.findIndex((item) => _.isEqual(item, before)) === -1
      )
    },
    addedItems() {
      const itemsAfter = this.entry.after[this.fieldIdentifier]
      const itemsBefore = this.entry.before[this.fieldIdentifier] || []
      if (!itemsAfter) {
        return []
      }
      return itemsAfter.filter(
        (after) =>
          itemsBefore.findIndex((item) => _.isEqual(item, after)) === -1
      )
    },
  },
  methods: {
    name(item) {
      // if item is a number, wrap it in an object as the getCollaboratorName expects
      if (typeof item === 'number') {
        item = { id: item }
      }
      return this.getCollaboratorName(item, this.store)
    },
    initials(name) {
      return name.slice(0, 1).toUpperCase()
    },
  },
}
</script>
