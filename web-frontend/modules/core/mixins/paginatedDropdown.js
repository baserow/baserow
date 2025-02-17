import debounce from 'lodash/debounce'

import dropdown from '@baserow/modules/core/mixins/dropdown'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'paginatedDropdown',
  mixins: [dropdown],
  props: {
    // The attribute name that contains the identifier in the fetched results.
    idName: {
      type: String,
      required: false,
      default: 'id',
    },
    // The attribute name that contains the display value in the fetched results.
    valueName: {
      type: String,
      required: false,
      default: 'value',
    },
    fetchOnOpen: {
      type: Boolean,
      required: false,
      default: false,
    },
    addEmptyItem: {
      type: Boolean,
      required: false,
      default: true,
    },
    emptyItemDisplayName: {
      type: [String],
      default: '',
    },
    notSelectedText: {
      type: [String, null],
      required: false,
      default: null,
    },
    initialDisplayName: {
      type: [String, null],
      required: false,
      default: null,
    },
    debounceTime: {
      type: Number,
      required: false,
      default: 400,
    },
    pageSize: {
      type: Number,
      required: false,
      default: 20,
    },
    includeDisplayNameInSelectedEvent: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      fetched: false,
      displayName: this.initialDisplayName,
      count: 0,
      page: 1,
      loading: false,
      results: [],
    }
  },
  /**
   * When the component is first created, we immediately fetch the first page.
   * If fetchOnOpen is true, we don't fetch the first page yet, but wait until
   * the dropdown is opened.
   */
  async fetch() {
    if (!this.fetchOnOpen) {
      await this.fetch(this.page, this.query)
    }
  },
  created() {
    // Small debounce when searching to prevent a lot of requests to the backend.
    this._search_debounced = debounce(async () => {
      await this.fetch(1, this.query)
    }, this.debounceTime)
  },
  methods: {
    clear() {
      this.displayName = this.initialDisplayName
    },
    /**
     * Because the dropdown items could be destroyed in case of a search and because we
     * don't need reactivity, we store a copy of the name as display name as soon as it
     * has changed.
     */
    select(value) {
      const displayName = this.getSelectedProperty(value, 'name')
      if (this.includeDisplayNameInSelectedEvent) {
        dropdown.methods.select.call(this, { value, displayName })
      } else {
        dropdown.methods.select.call(this, value)
      }
      this.displayName = displayName
    },
    /**
     * Fetches a page of results from the backend. The page and search query can be
     * provided as arguments. If replace is true, the results will replace the current
     * results, otherwise they will be appended.
     */
    async fetch(page = 1, search = null, replace = true) {
      this.fetched = true
      this.page = page
      this.loading = true
      let results = []
      let count = 0

      try {
        const { data } = await this.fetchPage(page, search)
        results = data.results
        count = data.count
      } catch (e) {
        notifyIf(e)
      } finally {
        if (replace) {
          this.results = results
        } else {
          const resultIds = new Set(this.results.map((res) => res.id))
          this.results.push(
            ...results.filter((res) => {
              return !resultIds.has(res.id)
            })
          )
        }

        this.count = count
        this.loading = false
      }
    },
    /**
     * Because the results change when you search, we need to reset the state before
     * searching. Otherwise there could be conflicting results.
     */
    search() {
      this._search_debounced()
    },
    /**
     * When the user scrolls in the results, we can check if the user is near the end
     * and if so a new page will be loaded.
     */
    async scroll() {
      const items = this.$refs.items
      const max = items.scrollHeight - items.clientHeight

      if (
        !this.loading &&
        this.results.length < this.count &&
        items.scrollTop > max - 30
      ) {
        await this.fetch(this.page + 1, this.query, false)
      }
    },
    async show(...args) {
      dropdown.methods.show.call(this, ...args)
      if (!this.fetched) {
        await this.fetch(this.page, this.query)
      }
    },
    /**
     * Normally, when the dropdown hides, the search is reset, but in this case we
     * don't want to do that because otherwise results are refreshed everytime the
     * user closes dropdown.
     */
    hide() {
      this.open = false
      this.$emit('hide')
    },
    reset() {
      this.fetched = false
      this.open = false
      this.displayName = null
      this.query = ''
      this.results = []
    },
  },
}
