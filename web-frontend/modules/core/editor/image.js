import { Image } from '@tiptap/extension-image'
import { Plugin, TextSelection } from '@tiptap/pm/state'

import { isTrustedImageUrl } from '@baserow/modules/core/editor/trustedImageUrls'

// `![alt][name](url)`, the URL optional; same ASCII-only grammar as `rich_text_utils.py`.
const IMAGE_REF_REGEX =
  /^!\[([^[\]\\]*(?:\\[^\n][^[\]\\]*)*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\] \t\n\r\f\v/\\()]*)\](?:\(([^() \t\n\r\f\v]+)\))?/

const escapeAlt = (s) => s.replace(/[\\[\]]/g, '\\$&')
const unescapeAlt = (s) => s.replace(/\\([\\[\]])/g, '$1')

function imageMarkdown({ alt, src, title, userFileName }) {
  const escapedAlt = escapeAlt(alt || '')
  if (userFileName) {
    // No `()` when unresolved: an empty group is not the storage format and piles up on each save.
    return src
      ? `![${escapedAlt}][${userFileName}](${src})`
      : `![${escapedAlt}][${userFileName}]`
  }
  return title
    ? `![${escapedAlt}](${src || ''} "${title}")`
    : `![${escapedAlt}](${src || ''})`
}

const isPendingImage = (node) =>
  node.type.name === 'image' && Boolean(node.attrs.uploadId)

const isPendingImageJSON = (node) =>
  node.type === 'image' && Boolean(node.attrs?.uploadId)

const isParagraphMadeForPendingImages = (node) =>
  node.type === 'paragraph' &&
  node.content?.length > 0 &&
  node.content.every(isPendingImageJSON) &&
  node.content.some((child) => child.attrs.ownParagraph)

/** Returns the images still uploading in a document or fragment, as `{ node, pos }` in order. */
export function findPendingImages(content) {
  const found = []
  content.descendants((node, pos) => {
    if (isPendingImage(node)) {
      found.push({ node, pos })
    }
  })
  return found
}

// A code block only holds plain text, so the image goes after it instead of splitting it.
function imageInsertPosition(doc, pos) {
  const $pos = doc.resolve(pos)
  for (let depth = $pos.depth; depth > 0; depth -= 1) {
    if ($pos.node(depth).type.spec.code) {
      return $pos.after(depth)
    }
  }
  return pos
}

/** Adds one pending image per upload id at `pos`, in order, with the caret after them. */
export function insertPendingImages(tr, pos, uploadIds) {
  const imageType = tr.doc.type.schema.nodes.image
  const insertAt = imageInsertPosition(tr.doc, pos)
  const ownParagraph = !tr.doc.resolve(insertAt).parent.inlineContent
  const stepCount = tr.steps.length
  tr.insert(
    insertAt,
    uploadIds.map((uploadId) => imageType.create({ uploadId, ownParagraph }))
  )
  const end = tr.mapping.slice(stepCount).map(insertAt)
  return tr.setSelection(TextSelection.near(tr.doc.resolve(end), -1))
}

function deletePendingImage(tr, node, pos) {
  const $pos = tr.doc.resolve(pos)
  // A lone paragraph stays, since the node around it must keep a block.
  const removesParagraph =
    node.attrs.ownParagraph &&
    $pos.parent.childCount === 1 &&
    $pos.node(-1).childCount > 1
  if (removesParagraph) {
    tr.delete($pos.before(), $pos.after())
  } else {
    tr.delete(pos, pos + node.nodeSize)
  }
}

/** Gives each settled pending image its uploaded attributes, or removes it when they are `null`. */
function settlePendingImages(tr, settledUploads) {
  findPendingImages(tr.doc)
    .reverse()
    .forEach(({ node, pos }) => {
      const { uploadId } = node.attrs
      if (!settledUploads.has(uploadId)) {
        return
      }
      const attrs = settledUploads.get(uploadId)
      if (attrs === null) {
        deletePendingImage(tr, node, pos)
        return
      }
      Object.entries({ ...attrs, uploadId: null, ownParagraph: false }).forEach(
        ([name, value]) => tr.setNodeAttribute(pos, name, value)
      )
    })
  return tr
}

const bringsPendingImage = (transaction) =>
  transaction.steps.some(
    (step) => step.slice && findPendingImages(step.slice.content).length > 0
  )

/** Copies `json` without pending images, which are not content yet, or the paragraphs made for them. */
export function withoutPendingImages(json) {
  if (!Array.isArray(json?.content) || json.content.length === 0) {
    return json
  }
  const content = json.content
    .filter(
      (child) =>
        !isPendingImageJSON(child) && !isParagraphMadeForPendingImages(child)
    )
    .map(withoutPendingImages)
  if (content.length > 0) {
    return { ...json, content }
  }
  const { content: removed, ...withoutContent } = json
  return removed.some(isParagraphMadeForPendingImages)
    ? { ...withoutContent, content: [{ type: 'paragraph' }] }
    : withoutContent
}

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
      // Set only while the upload is in progress, and never taken from pasted content.
      uploadId: {
        default: null,
        rendered: false,
        parseHTML: () => null,
      },
      // Set on a pending image whose paragraph was made for it, so that paragraph goes with it.
      ownParagraph: {
        default: false,
        rendered: false,
        parseHTML: () => false,
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
  addStorage() {
    return { settledUploads: new Map() }
  },
  addCommands() {
    return {
      ...this.parent?.(),
      settlePendingImage:
        (uploadId, attrs) =>
        ({ tr, dispatch }) => {
          if (dispatch) {
            this.storage.settledUploads.set(uploadId, attrs)
            settlePendingImages(tr, this.storage.settledUploads).setMeta(
              'addToHistory',
              false
            )
          }
          return true
        },
    }
  },
  addProseMirrorPlugins() {
    const { settledUploads } = this.storage
    return [
      ...(this.parent?.() ?? []),
      new Plugin({
        // Undo and redo can bring back a pending image whose upload has settled since.
        appendTransaction: (transactions, oldState, newState) => {
          if (
            settledUploads.size === 0 ||
            !transactions.some(bringsPendingImage)
          ) {
            return null
          }
          const tr = settlePendingImages(newState.tr, settledUploads)
          return tr.docChanged ? tr.setMeta('addToHistory', false) : null
        },
      }),
    ]
  },
  renderHTML({ node, HTMLAttributes }) {
    if (node.attrs.uploadId) {
      return ['span', { class: 'rich-text-editor__image-uploading' }]
    }
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
    if (node.attrs?.uploadId) {
      return ''
    }
    const markdown = imageMarkdown(node.attrs ?? {})
    const link = node.markdownLink
    if (!link) {
      return markdown
    }
    const href = link.href ?? ''
    return link.title
      ? `[${markdown}](${href} "${link.title}")`
      : `[${markdown}](${href})`
  },
})
