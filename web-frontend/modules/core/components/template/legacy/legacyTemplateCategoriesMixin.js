import { clone } from '@baserow/modules/core/utils/object'
import { escapeRegExp } from '@baserow/modules/core/utils/string'
import {
  getCategoryName,
  sortCategories,
} from '@baserow/modules/core/utils/templateCategory'

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
    categoryI18n() {
      return { t: this.$t, te: this.$te, locale: this.$i18n.locale }
    },
    /**
     * Returns the categories and templates that match the search query.
     */
    matchingCategories() {
      const categories = sortCategories(this.categories, this.categoryI18n)
      if (this.search === '') {
        return categories
      }

      return clone(categories)
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
    categoryName(category) {
      return getCategoryName(category, this.categoryI18n)
    },
    selectCategory(id) {
      this.selectedCategoryId = this.selectedCategoryId === id ? -1 : id
    },
  },
}
