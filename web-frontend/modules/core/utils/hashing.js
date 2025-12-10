import { sha256 } from 'js-sha256'

export function generateHash(value) {
  // TODO MIG do we want to use browser async version
  return sha256(value)
}
