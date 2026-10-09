/**
 * Search aliases are kept as one comma-separated locale string per type, so
 * every language can add its own terms through Weblate. This turns such a
 * string into the list of terms the add-node menu matches against.
 * @param {string} value - e.g. "loop, for loop, repeat"
 * @returns {string[]} - e.g. ["loop", "for loop", "repeat"]
 */
export function parseAliases(value) {
  return String(value || '')
    .split(',')
    .map((alias) => alias.trim())
    .filter(Boolean)
}
