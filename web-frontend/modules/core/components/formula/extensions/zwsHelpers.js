export const ZWS = '\u200B'
export const ZWS_REGEX = /\u200B/g
export const CONSECUTIVE_ZWS_REGEX = /\u200B+/g

export function isZWSNode(node) {
  return node?.isText && node.text && /^\u200B+$/.test(node.text)
}

export function zwsTextJSON() {
  return { type: 'text', text: ZWS }
}

export function zwsTextNode(schema) {
  return schema.text(ZWS)
}
