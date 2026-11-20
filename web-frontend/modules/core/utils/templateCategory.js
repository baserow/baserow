import { unref } from 'vue'

/**
 * The category's name in the user's language. The stored English name is the
 * translation key, so a category without a translation shows as stored.
 */
export function getCategoryName(category, i18n) {
  const key = `templateCategoryNames.${category.name}`
  return i18n.te(key) ? i18n.t(key) : category.name
}

function sortKey(category, i18n) {
  return getCategoryName(category, i18n).replace(/^[^\p{L}\p{N}]+/u, '')
}

/**
 * The categories sorted by their shown name. A leading emoji is ignored, like the
 * database does when it sorts the stored names.
 */
export function sortCategories(categories, i18n) {
  return [...categories].sort((a, b) =>
    sortKey(a, i18n).localeCompare(sortKey(b, i18n), unref(i18n.locale))
  )
}
