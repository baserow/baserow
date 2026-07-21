const PALETTE = [
  '#4C6EF5',
  '#7950F2',
  '#BE4BDB',
  '#E64980',
  '#FA5252',
  '#FD7E14',
  '#FAB005',
  '#40C057',
  '#12B886',
  '#15AABF',
  '#228BE6',
  '#3B5BDB',
  '#6741D9',
  '#9C36B5',
  '#C2255C',
  '#E8590C',
  '#F08C00',
  '#2F9E44',
  '#099268',
  '#0C8599',
]

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `${r}, ${g}, ${b}`
}

const PALETTE_RGB = PALETTE.map(hexToRgb)

export const ANONYMOUS_USER_ID = -1

function _colorIndex(userId) {
  return (Math.imul(userId, 2654435761) >>> 0) % PALETTE.length
}

function _stringHash(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0
  }
  return (h >>> 0) % PALETTE.length
}

export function getAnonymousDisplayName(presenceId) {
  return `Anonymous #${(presenceId || '').slice(0, 4)}`
}

export function getPresenceColor(userId, presenceId) {
  if (userId === ANONYMOUS_USER_ID && presenceId) {
    return PALETTE[_stringHash(presenceId)]
  }
  return PALETTE[_colorIndex(userId)]
}

export function getPresenceColorRgb(userId, presenceId) {
  if (userId === ANONYMOUS_USER_ID && presenceId) {
    return PALETTE_RGB[_stringHash(presenceId)]
  }
  return PALETTE_RGB[_colorIndex(userId)]
}
