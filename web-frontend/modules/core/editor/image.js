import { Image } from '@tiptap/extension-image'

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
  renderMarkdown(node) {
    const esc = (s) => s.replace(/[[\]()]/g, '\\$&')
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
