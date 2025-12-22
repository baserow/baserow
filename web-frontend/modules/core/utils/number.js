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

export const sum = (arr, { strict = false } = {}) => {
  return arr.reduce((total, val) => {
    const num = Number(val)
    if (Number.isFinite(num)) {
      return total + num
    } else if (strict) {
      throw new Error(`Invalid number: ${val}`)
    }
    return total
  }, 0)
}

export const avg = (arr, { strict = false } = {}) => {
  let validNumbers = 0
  const _sum = arr.reduce((total, val) => {
    const num = Number(val)
    if (Number.isFinite(num)) {
      validNumbers++
      return total + num
    } else if (strict) {
      throw new Error(`Invalid number: ${val}`)
    }
    return total
  }, 0)
  if (validNumbers > 0) {
    return _sum / validNumbers
  }
  return _sum
}
