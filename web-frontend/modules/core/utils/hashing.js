import { sha256 } from 'js-sha256'

export function generateHash(value) {
  if (Number.isInteger(value)) {
    value = String(value)
  }

  return sha256(value)
}
