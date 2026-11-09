import { getUrlScheme } from '@baserow/modules/core/utils/url'

// Parse in an inert document so validating a draft cannot load its resources.
// Move these exact nodes into the live page only after validating the whole tree.
export function parseStaticHTML(html) {
  const template = document.createElement('template')
  const container = template.content.ownerDocument.createElement('div')
  container.innerHTML = html
  const roots = [container]
  for (const root of roots) {
    for (const node of root.querySelectorAll('*')) {
      const tag = node.localName.toLowerCase()
      if (tag === 'script') return null
      if (node.content?.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
        roots.push(node.content)
      }
      for (const attr of node.attributes) {
        const name = attr.localName.toLowerCase()
        if (name.startsWith('on') || name === 'srcdoc') return null
        if (urlAttributes.has(name)) {
          const scheme = getUrlScheme(attr.value)
          if (scheme === 'javascript:') return null
          if (['iframe', 'object', 'embed'].includes(tag) && scheme === 'data:')
            return null
        }
        if (['animate', 'set'].includes(tag) && name === 'attributename') {
          const target = attr.value.toLowerCase().split(':').pop()
          if (urlAttributes.has(target) || target.startsWith('on')) return null
        }
      }
    }
  }
  const fragment = container.ownerDocument.createDocumentFragment()
  while (container.firstChild) fragment.append(container.firstChild)
  return fragment
}

const urlAttributes = new Set([
  'href',
  'xlink:href',
  'src',
  'action',
  'formaction',
  'data',
  'codebase',
])
