// Redis IDs are decimal pairs, not gapless sequence numbers. Keep them as strings
// so millisecond IDs and future values cannot lose integer precision.
export function parseCursor(cursor) {
  const match = /^([^:]+):(\d+)-(\d+)$/.exec(cursor || '')
  return match ? { generation: match[1], parts: match.slice(2) } : null
}

export function compareCursors(left, right) {
  const a = parseCursor(left)
  const b = parseCursor(right)
  if (!a || !b || a.generation !== b.generation) return null
  for (let i = 0; i < 2; i++) {
    const x = a.parts[i].replace(/^0+(?=\d)/, '')
    const y = b.parts[i].replace(/^0+(?=\d)/, '')
    if (x.length !== y.length) return x.length > y.length ? 1 : -1
    if (x !== y) return x > y ? 1 : -1
  }
  return 0
}
