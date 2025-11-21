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

export const sum = (arr) => {
  return arr.reduce((total, val) => {
    const num = Number(val)
    return Number.isFinite(num) ? total + num : total
  }, 0)
}
