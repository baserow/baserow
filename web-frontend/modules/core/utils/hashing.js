import crypto from 'crypto'

export async function generateHash(input) {
  const data = new TextEncoder().encode(input)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
  //return crypto.createHash('sha256').update(value.toString()).digest('hex')
}
