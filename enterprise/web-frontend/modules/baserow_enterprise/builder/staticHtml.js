const urlAttributes = new Set([
  'href',
  'xlink:href',
  'src',
  'action',
  'formaction',
  'poster',
  'cite',
  'background',
  'codebase',
])

function isExecutableURL(value, tag) {
  try {
    const { protocol } = new URL(value, 'https://example.invalid/')
    return (
      protocol === 'javascript:' ||
      (['iframe', 'object', 'embed'].includes(tag) && protocol === 'data:')
    )
  } catch {
    return false
  }
}

function* srcsetURLs(value) {
  const candidate = /[,\t\n\f\r ]*([^\t\n\f\r ]+)/gy
  const descriptors = /(?:[^,(]|\([^)]*(?:\)|$))*(?:,|$)/gy
  let match
  while ((match = candidate.exec(value))) {
    yield match[1].replace(/,+$/, '')
    if (!match[1].endsWith(',')) {
      descriptors.lastIndex = candidate.lastIndex
      descriptors.exec(value)
      candidate.lastIndex = descriptors.lastIndex
    }
  }
}

function isStaticNode(node, roots) {
  // Form controls can shadow native form properties, including attributes.
  const tag = Reflect.get(Element.prototype, 'localName', node).toLowerCase()
  if (tag === 'script') return false
  if (tag === 'template' && node.content) roots.push(node.content)
  const attrs = Object.fromEntries(
    Array.from(Reflect.get(Element.prototype, 'attributes', node), (attr) => [
      attr.name.toLowerCase(),
      attr.value,
    ])
  )
  for (const [name, value] of Object.entries(attrs)) {
    if (name.startsWith('on')) return false
    if (name === 'srcset' || name === 'imagesrcset') {
      for (const url of srcsetURLs(value)) {
        if (isExecutableURL(url, tag)) return false
      }
    }
    if (
      name === 'ping' &&
      value.split(/[\t\n\f\r ]+/).some((url) => isExecutableURL(url, tag))
    )
      return false
    if (
      (urlAttributes.has(name) || (tag === 'object' && name === 'data')) &&
      isExecutableURL(value, tag)
    )
      return false
  }
  if (tag === 'iframe' && attrs.srcdoc) {
    roots.push(new DOMParser().parseFromString(attrs.srcdoc, 'text/html'))
  }
  if (tag === 'meta' && attrs['http-equiv']?.toLowerCase() === 'refresh') {
    const url = (attrs.content ?? '').replace(
      /^\s*[.\d]+[\s;,]+(?:url\s*=\s*)?['"]?/i,
      ''
    )
    if (isExecutableURL(url, tag)) return false
  }
  if (['animate', 'set'].includes(tag)) {
    const target = (attrs.attributename ?? '')
      .trim()
      .toLowerCase()
      .split(':')
      .pop()
    if (target.startsWith('on') || ['srcdoc', 'attributename'].includes(target))
      return false
    if (
      urlAttributes.has(target) &&
      [...(attrs.values ?? '').split(';'), attrs.from, attrs.to, attrs.by].some(
        (value) => value && isExecutableURL(value, tag)
      )
    )
      return false
  }
  return true
}

// Render the exact nodes inspected by the browser, without reparsing the source
// in the live document. The template's owner document has no browsing context.
export function parseStaticHTML(html) {
  const inert = document.createElement('template').content.ownerDocument
  const container = inert.createElement('div')
  container.innerHTML = html
  const roots = [container]
  for (const root of roots) {
    for (const node of root.querySelectorAll('*')) {
      if (!isStaticNode(node, roots)) return null
    }
  }
  const fragment = inert.createDocumentFragment()
  while (container.firstChild) fragment.append(container.firstChild)
  return fragment
}
