/**
 * Long cards make the next one hard to find, so a section that opens with
 * two or more items shows them folded. Items added while the section is
 * open start expanded, because the user is about to configure them.
 */
export default {
  data() {
    return { initialCardIds: null }
  },
  methods: {
    cardInitiallyExpanded(item, items) {
      if (this.initialCardIds === null && items.length > 0) {
        this.initialCardIds = new Set(items.map(({ id }) => id))
      }
      if (this.initialCardIds === null || this.initialCardIds.size < 2) {
        return true
      }
      return !this.initialCardIds.has(item.id)
    },
  },
}
