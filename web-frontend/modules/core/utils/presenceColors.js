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

function _colorIndex(userId) {
  return ((userId * 2654435761) >>> 0) % PALETTE.length
}

export function getPresenceUserColor(userId) {
  return PALETTE[_colorIndex(userId)]
}

export function getPresenceUserColorRgb(userId) {
  return PALETTE_RGB[_colorIndex(userId)]
}
