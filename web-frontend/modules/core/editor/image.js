import { Image } from '@tiptap/extension-image'

import { isTrustedImageUrl } from '@baserow/modules/core/editor/trustedImageUrls'

// `![alt][name](url)`, the URL optional; same ASCII-only grammar as `rich_text_utils.py`.
const IMAGE_REF_REGEX =
  /^!\[([^[\]\\]*(?:\\[^\n][^[\]\\]*)*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\] \t\n\r\f\v/\\()]*)\](?:\(([^() \t\n\r\f\v]+)\))?/

const escapeAlt = (s) => s.replace(/[\\[\]]/g, '\\$&')
const unescapeAlt = (s) => s.replace(/\\([\\[\]])/g, '$1')

export const ScalableImage = Image.extend({
  selectable: true,
  addOptions() {
    // Inline so an image can sit in a paragraph or list item; CSS shows it on its own line.
    return { ...this.parent?.(), inline: true }
  },
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
    } else if (node.attrs.src) {
      // Lets an in-editor copy/paste keep an external image the placeholder hides.
      attrs['data-external-src'] = node.attrs.src
    }
    // Only URLs Baserow handed out are loaded; external images stay placeholders for now.
    if (!isTrustedImageUrl(node.attrs.src)) {
      const { src, ...rest } = attrs
      // The icon is a child element rather than the U+1F5BC glyph: Inter does
      // not cover that codepoint, so the browser picked the colour emoji font
      // on some pages and a monochrome one on others.
      return [
        'span',
        { ...rest, class: 'rich-text-editor__image-placeholder' },
        [
          'i',
          {
            class: 'iconoir-media-image rich-text-image-placeholder',
            'aria-hidden': 'true',
          },
        ],
        node.attrs.alt ? ` ${node.attrs.alt}` : '',
      ]
    }
    return ['img', attrs]
  },
  parseHTML() {
    return [
      {
        tag: 'span[data-external-src]',
        getAttrs(dom) {
          return {
            src: dom.getAttribute('data-external-src'),
            alt: dom.getAttribute('alt'),
            title: dom.getAttribute('title'),
          }
        },
      },
      {
        // The placeholder rendered for an unresolved reference. Without this
        // the span would paste back as literal text and the reference would be
        // lost, because the rule below only matches `img`.
        tag: 'span[data-user-file-name]',
        getAttrs(dom) {
          return {
            src: '',
            alt: dom.getAttribute('alt'),
            title: dom.getAttribute('title'),
            userFileName: dom.getAttribute('data-user-file-name'),
          }
        },
      },
      {
        tag: 'img[src]',
        getAttrs(dom) {
          const src = dom.getAttribute('src') || ''
          const userFileName = dom.getAttribute('data-user-file-name')
          if (!userFileName) {
            // Pasting a web page must not bring its images in as placeholders.
            return false
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
    return helpers.createNode('image', {
      src: token.src ?? token.href ?? '',
      alt: token.alt ?? token.text ?? '',
      title: token.title ?? null,
      userFileName: token.userFileName ?? null,
    })
  },
  renderMarkdown(node) {
    const alt = node.attrs?.alt || ''
    const src = node.attrs?.src || ''
    if (node.attrs?.userFileName) {
      // No `()` when the URL is unresolved: an empty group is not the storage
      // format, and it accumulates over repeated saves.
      return src
        ? `![${escapeAlt(alt)}][${node.attrs.userFileName}](${src})`
        : `![${escapeAlt(alt)}][${node.attrs.userFileName}]`
    }
    const title = node.attrs?.title || ''
    if (title) {
      return `![${escapeAlt(alt)}](${src} "${title}")`
    }
    return `![${escapeAlt(alt)}](${src})`
  },
})
