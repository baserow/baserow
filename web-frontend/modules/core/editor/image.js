import { Image } from '@tiptap/extension-image'

const IMAGE_REF_REGEX =
  /^!\[([^[\]]*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s]+)\](?:\(([^)]+)\))?/

export const ScalableImage = Image.extend({
  selectable: true,
  addAttributes() {
    return {
      ...this.parent?.(),
      userFileName: {
        default: null,
        rendered: false,
      },
      maxWidth: {
        default: '100%',
        renderHTML: (attributes) => {
          return {
            style: `max-width: ${attributes.maxWidth}; height: auto;`,
          }
        },
      },
    }
  },
  renderHTML({ HTMLAttributes }) {
    const attrs = { ...HTMLAttributes }
    if (attrs.userFileName) {
      attrs['data-user-file-name'] = attrs.userFileName
    }
    delete attrs.userFileName
    return ['img', attrs]
  },
  parseHTML() {
    return [
      {
        tag: 'img[src]',
        getAttrs(dom) {
          return {
            src: dom.getAttribute('src'),
            alt: dom.getAttribute('alt'),
            title: dom.getAttribute('title'),
            userFileName: dom.getAttribute('data-user-file-name') || null,
          }
        },
      },
    ]
  },
  markdownTokenName: 'image',
  markdownTokenizer: {
    name: 'baserowImage',
    level: 'inline',
    start(source) {
      return source.indexOf('![')
    },
    tokenize(source) {
      const match = source.match(IMAGE_REF_REGEX)
      if (!match) {
        return undefined
      }
      return {
        type: 'image',
        raw: match[0],
        alt: match[1],
        userFileName: match[2],
        src: match[3] || '',
      }
    },
  },
  parseMarkdown(token, helpers) {
    return helpers.createNode('image', {
      src: token.src ?? token.href ?? '',
      alt: token.alt ?? token.text ?? '',
      userFileName: token.userFileName ?? null,
    })
  },
  renderMarkdown(node) {
    const esc = (s) => s.replace(/[\\[\]]/g, '\\$&')
    const alt = node.attrs?.alt || ''
    if (node.attrs?.userFileName) {
      const src = node.attrs?.src || ''
      return `![${esc(alt)}][${node.attrs.userFileName}](${src})`
    }
    const src = node.attrs?.src || ''
    const title = node.attrs?.title || ''
    if (title) {
      return `![${esc(alt)}](${src} "${title}")`
    }
    return `![${esc(alt)}](${src})`
  },
})
