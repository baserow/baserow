import paginatedDropdown from '@baserow/modules/core/mixins/paginatedDropdown'
import dropdown from '@baserow/modules/core/mixins/dropdown'

export default {
  name: 'inMemoryPaginatedDropdown',
  mixins: [paginatedDropdown],
  methods: {
    fetchPage(page = 1, query = '') {
      const start = (page - 1) * this.pageSize
      const results = this.filterItems(query || '')
      return {
        data: {
          count: results.length,
          results: results.slice(start, start + this.pageSize),
        },
      }
    },
    search() {
      this.fetch(1, this.query)
    },
    hide() {
      // Call the dropdown `hide` method because it resets the search. We're
      // deliberately not inheriting the `paginatedDropdown` method because that one
      // doesn't reset the search because then another reset is made.
      return dropdown.methods.hide.call(this)
    },
  },
}
