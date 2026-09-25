import { InputRule } from '@tiptap/core'
import { Image } from '@tiptap/extension-image'
import { isAllowedUri } from '@tiptap/extension-link'

import { LINK_PROTOCOLS } from '@baserow/modules/core/editor/linkProtocols'
import { isTrustedImageUrl } from '@baserow/modules/core/editor/trustedImageUrls'

// `![alt][userFileName](url)`: alt allows backslash escapes (linear, ReDoS-safe),
// the name may not contain path separators and its extension may be empty, the
// URL is optional because the backend strips it on write and re-appends it on
// read. The URL excludes `(` and whitespace so a missing `)` stops the scan at
// the next `(` rather than at the end of the input.
const IMAGE_REF_REGEX =
  /^!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\()]*)\](?:\(([^()\s]+)\))?/

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
    // Only a URL Baserow handed out (see `trustedImageUrls`) is loaded. A
    // reference the backend has not resolved yet has no URL, and one pasted as
    // HTML may carry any `src`; both show the alt text instead. The node keeps
    // `userFileName` and `src`, so serializing it back still produces the
    // reference, which the backend resolves on save: the placeholder is
    // display only.
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
            // Rich text images are Baserow user files only. An external image
            // (pasted HTML) is not an image node here, whatever its protocol:
            // it would be loaded by every reader of a public view, from a host
            // the workspace does not control. See `parseMarkdown` below, which
            // keeps the same rule for the markdown path.
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
  addInputRules() {
    // The base rule turns a typed `![alt](url)` into an image loaded from any
    // host. Rich text images are Baserow uploads only, so the typed syntax
    // degrades to a link, like a plain markdown image does on parse.
    return [
      new InputRule({
        find: /(?:^|\s)(!\[([^[\]\n]*)\]\((\S+)\))$/,
        handler: ({ state, range, match }) => {
          const [, token, alt, src] = match
          const start = range.from + match[0].indexOf(token)
          const text = alt || src
          const link = state.schema.marks.link
          const marks =
            link && isAllowedUri(src, LINK_PROTOCOLS)
              ? [link.create({ href: src })]
              : []
          state.tr.replaceWith(start, range.to, state.schema.text(text, marks))
        },
      }),
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
      // Plain `![alt](url)` — an external image, which is not supported: rich
      // text images are Baserow user files only. It degrades to a link so the
      // URL stays visible and the reader chooses whether to follow it, instead
      // of the page loading it for them.
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
