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

export function getPresenceUserColor(userId) {
  const hash = ((userId * 2654435761) >>> 0) % PALETTE.length
  return PALETTE[hash]
}
