/**
 * happy-dom defines an element's `nodeName` on `Element.prototype` and returns
 * an empty string from the `Node.prototype` getter. DOMPurify reads names
 * through the `Node.prototype` getter, so a page can't spoof them, and without
 * this every element looks unknown to it. Makes the base getter return the
 * same name as the node's own class, like a browser does.
 */
const base = Object.getOwnPropertyDescriptor(Node.prototype, 'nodeName')

if (base.get.call(document.createElement('p')) === '') {
  Object.defineProperty(Node.prototype, 'nodeName', {
    ...base,
    get() {
      let proto = Object.getPrototypeOf(this)
      while (proto && proto !== Node.prototype) {
        const own = Object.getOwnPropertyDescriptor(proto, 'nodeName')
        if (own?.get) {
          return own.get.call(this)
        }
        proto = Object.getPrototypeOf(proto)
      }
      return base.get.call(this)
    },
  })
}
