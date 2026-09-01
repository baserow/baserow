/**
 * Checks whether a workspace or application matches the all workspaces search
 * query. The name is matched case insensitively as a substring. A query consisting
 * of digits only additionally matches the id by prefix, so that typing `12` already
 * finds id `123` while the user is still typing.
 */
export function matchesQuery(name, id, rawQuery) {
  const query = rawQuery.trim().toLowerCase()

  if (query === '') {
    return false
  }

  if (name.toLowerCase().includes(query)) {
    return true
  }

  return /^\d+$/.test(query) && String(id).startsWith(query)
}

/**
 * Lowercases the text while remembering, for every code unit of the lowered text,
 * the start and end offset of the original character that produced it.
 * `toLowerCase` can expand one character into several code units (e.g. `İ`), so
 * offsets found in the lowered text can't be applied to the original directly.
 */
function toLowerCaseWithOffsets(text) {
  let lowered = ''
  const starts = []
  const ends = []
  let position = 0

  for (const character of text) {
    const loweredCharacter = character.toLowerCase()
    for (let i = 0; i < loweredCharacter.length; i++) {
      starts.push(position)
      ends.push(position + character.length)
    }
    lowered += loweredCharacter
    position += character.length
  }

  return { lowered, starts, ends }
}

/**
 * Splits the text into segments covering every case insensitive occurrence of the
 * query, so that matches can be highlighted without `v-html`. Uses the same
 * lowercasing as `matchesQuery`, so everything that matches is also highlighted,
 * and always returns segments that concatenate back to the original text.
 */
export function splitHighlight(text, rawQuery) {
  const query = rawQuery.trim().toLowerCase()

  if (query === '') {
    return [{ text, matched: false }]
  }

  const segments = []
  const { lowered, starts, ends } = toLowerCaseWithOffsets(text)
  let position = 0
  let index = lowered.indexOf(query)

  while (index !== -1) {
    const start = starts[index]
    const end = ends[index + query.length - 1]

    if (start > position) {
      segments.push({ text: text.slice(position, start), matched: false })
    }

    segments.push({ text: text.slice(start, end), matched: true })
    position = end

    // A match can end halfway an expanded character, in which case the search
    // must continue after that whole character to keep the segments contiguous.
    let next = index + query.length
    while (next < lowered.length && starts[next] < end) {
      next++
    }
    index = lowered.indexOf(query, next)
  }

  if (position < text.length) {
    segments.push({ text: text.slice(position), matched: false })
  }

  return segments
}

/**
 * Selecting none or all of the application types both mean the user isn't
 * filtering, so the label and the filtering must agree on that rule.
 */
export function isTypeFilterActive(selectedTypes, applicationTypeCount) {
  return selectedTypes.length > 0 && selectedTypes.length < applicationTypeCount
}
