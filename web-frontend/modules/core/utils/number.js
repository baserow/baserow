export const rounder = (digits) => {
  return parseInt('1' + Array(digits + 1).join('0'))
}

export const floor = (n, digits = 0) => {
  const r = rounder(digits)
  return Math.floor(n * r) / r
}

export const ceil = (n, digits = 0) => {
  const r = rounder(digits)
  return Math.ceil(n * r) / r
}

export const clamp = (value, min, max) => {
  return Math.max(min, Math.min(value, max))
}

/**
 * Limits a number to a maximum value, useful for limiting runs
 * @param {number} value - The value to limit
 * @param {number} limit - The maximum allowed value
 * @returns {number} The limited value
 */
export const limitRuns = (value, limit) => {
  return Math.min(value, limit)
}
