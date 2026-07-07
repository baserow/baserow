export function activeFocusEntry(entries) {
  if (entries.length === 0) {
    return null
  }
  return entries.find((entry) => entry.editing) || entries[0]
}
