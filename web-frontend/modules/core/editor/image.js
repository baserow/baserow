import { Image } from '@tiptap/extension-image'
import { isAllowedUri } from '@tiptap/extension-link'

import { LINK_PROTOCOLS } from '@baserow/modules/core/editor/linkProtocols'
import { isSafeImageSrc } from '@baserow/modules/core/editor/richTextImageUtils'

// `![alt][userFileName](url)`: alt allows backslash escapes (linear, ReDoS-safe),
// the name may not contain path separators, the URL is optional because the
// backend strips it on write and re-appends it on read.
const IMAGE_REF_REGEX =
  /^!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\]+)\](?:\(([^)]+)\))?/

const escapeAlt = (s) => s.replace(/[\\[\]]/g, '\\$&')
const unescapeAlt = (s) => s.replace(/\\([\\[\]])/g, '$1')

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
  renderHTML({ node, HTMLAttributes }) {
    // `rendered: false` keeps userFileName out of HTMLAttributes, so read it from
    // the node. ProseMirror's clipboard prefers text/html, and without this
    // attribute an in-editor copy/paste drops the user file ref.
    const attrs = { ...HTMLAttributes }
    if (node.attrs.userFileName) {
      attrs['data-user-file-name'] = node.attrs.userFileName
    }
    return ['img', attrs]
  },
  parseHTML() {
    return [
      {
        tag: 'img[src]',
        getAttrs(dom) {
          const src = dom.getAttribute('src') || ''
          const userFileName = dom.getAttribute('data-user-file-name')
          if (!userFileName) {
            // External image (pasted HTML). Same predicate as the markdown
            // path so the two cannot drift.
            if (!isSafeImageSrc(src)) {
              return false
            }
          }
          return {
            src,
            alt: dom.getAttribute('alt'),
            title: dom.getAttribute('title'),
            userFileName: userFileName || null,
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
        alt: unescapeAlt(match[1]),
        userFileName: match[2],
        src: match[3] || '',
      }
    },
  },
  parseMarkdown(token, helpers) {
    const src = token.src ?? token.href ?? ''
    const alt = token.alt ?? token.text ?? ''
    if (!token.userFileName) {
      // Plain `![alt](url)` — external image. Unsafe protocols fall through
      // to a link, everything else to text.
      if (src && isSafeImageSrc(src)) {
        return helpers.createNode('image', { src, alt })
      }
      const text = alt || src
      if (!text) {
        return null
      }
      if (src && isAllowedUri(src, LINK_PROTOCOLS)) {
        return helpers.createTextNode(text, [
          { type: 'link', attrs: { href: src } },
        ])
      }
      return helpers.createTextNode(text)
    }
    return helpers.createNode('image', {
      src,
      alt,
      userFileName: token.userFileName,
    })
  },
  renderMarkdown(node) {
    const alt = node.attrs?.alt || ''
    const src = node.attrs?.src || ''
    if (node.attrs?.userFileName) {
      return `![${escapeAlt(alt)}][${node.attrs.userFileName}](${src})`
    }
    const title = node.attrs?.title || ''
    if (title) {
      return `![${escapeAlt(alt)}](${src} "${title}")`
    }
    return `![${escapeAlt(alt)}](${src})`
  },
})
