import { clone } from '@baserow/modules/core/utils/object'
import { escapeRegExp } from '@baserow/modules/core/utils/string'

export default {
  props: {
    categories: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      search: '',
      selectedCategoryId: -1,
    }
  },
  computed: {
    /**
     * Returns the categories and templates that match the search query.
     */
    matchingCategories() {
      if (this.search === '') {
        return this.categories
      }

      return clone(this.categories)
        .map((category) => {
          category.templates = category.templates.filter((template) => {
            const keywords = template.keywords.split(',')
            keywords.push(template.name)
            const regex = new RegExp('(' + escapeRegExp(this.search) + ')', 'i')
            return keywords.some((value) => value.match(regex))
          })
          return category
        })
        .filter((category) => category.templates.length > 0)
    },
  },
  methods: {
    selectCategory(id) {
      this.selectedCategoryId = this.selectedCategoryId === id ? -1 : id
    },
  },
}
