import Markdown from 'markdown-it'
import markdownItImage from 'markdown-it/lib/rules_inline/image.mjs'
import taskLists from 'markdown-it-task-lists'
import { MarkdownManager } from '@tiptap/markdown'

import { IMAGE_REF_REGEX } from '@baserow/modules/core/editor/image'
import { parseMention } from '@baserow/modules/core/editor/mention'
import {
  configureMarkdownSerializerCompatibility,
  prepareMarkdownDocumentForSerialization,
} from '@baserow/modules/core/editor/markdownCompatibility'
import {
  createMarkedInstance,
  createRichTextContentExtensions,
  MARKDOWN_OPTIONS,
} from '@baserow/modules/core/editor/richTextExtensions'
import {
  IMAGE_PLACEHOLDER,
  preprocessRichTextImages,
  renderImagePlaceholders,
  stripImageUrls,
  stripUnresolvedImageRefs,
} from '@baserow/modules/core/editor/richTextImageUtils'

const previewMarkdownManager = new MarkdownManager({
  extensions: createRichTextContentExtensions({ enableImages: true }),
  marked: createMarkedInstance(),
  markedOptions: MARKDOWN_OPTIONS,
})
configureMarkdownSerializerCompatibility(previewMarkdownManager)

const makeEmptyParagraphsVisible = (node) => {
  if (node.type === 'paragraph' && !node.content?.length) {
    node.content = [{ type: 'text', text: '\u00a0' }]
    return true
  }

  return (
    node.content?.reduce(
      (found, child) => makeEmptyParagraphsVisible(child) || found,
      false
    ) ?? false
  )
}

// Only sentinels and blank-line runs can produce empty paragraphs on parse.
const EMPTY_PARAGRAPH_HINT_REGEXP = /&nbsp;|\u00a0|\n[ \t\r]*\n[ \t\r]*\n/

const prepareMarkdownForPreview = (value) => {
  // Parsing every value is too costly for grid cell previews, so gate it.
  if (!EMPTY_PARAGRAPH_HINT_REGEXP.test(value)) {
    return value
  }
  const document = previewMarkdownManager.parse(value)
  return makeEmptyParagraphsVisible(document)
    ? previewMarkdownManager.serialize(
        prepareMarkdownDocumentForSerialization(document)
      )
    : value
}

// Parity with the editor, which has no image node when images are off.
const literalImage = (state, silent) => {
  const start = state.pos
  const reference = IMAGE_REF_REGEX.exec(state.src.slice(start, state.posMax))
  if (reference) {
    state.pos += reference[0].length
  } else if (!markdownItImage(state, true)) {
    return false
  }
  if (!silent) {
    state.push('text', '', 0).content = state.src.slice(start, state.pos)
  }
  return true
}

export const parseMarkdown = (
  value,
  {
    openLinkOnClick = false,
    enableImages = false,
    workspaceUsers = null,
    loggedUserId = null,
  } = {}
) => {
  // Round trip first: after `preprocessRichTextImages` a reference has lost its file name.
  // A non-string, e.g. a cell still holding a value of the field's previous
  // type, would make markdown-it throw.
  const original = typeof value === 'string' ? value : ''
  let content = prepareMarkdownForPreview(original)

  const md = new Markdown({ html: false })
  // markdown-it normalises a destination before it lands in `src`, so the
  // resolved URLs are compared in the same form.
  let resolvedUrls = new Set()

  if (enableImages) {
    const { content: processed, nameMap } = preprocessRichTextImages(content)
    // The round trip can move text out of code, so only a URL the backend
    // resolved in the value itself is trusted.
    const originalNameMap =
      content === original
        ? nameMap
        : preprocessRichTextImages(original).nameMap
    resolvedUrls = new Set(
      Object.keys(nameMap)
        .filter((url) => originalNameMap[url] === nameMap[url])
        .map((url) => md.normalizeLink(url))
    )
    content = stripUnresolvedImageRefs(processed)
  } else {
    // The editor drops a resolved URL too, since the backend added it.
    content = stripImageUrls(content)
  }

  // task lists
  md.use(taskLists, { label: true, enabled: true })

  // link
  if (!openLinkOnClick) {
    // Remove the href attribute from the link to avoid the user clicking on it.
    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
      const hrefIndex = tokens[idx].attrIndex('href')
      if (hrefIndex >= 0) {
        tokens[idx].attrs.splice(hrefIndex, 1)
      }
      return self.renderToken(tokens, idx, options)
    }
  } else {
    // Add target="_blank" and rel="noopener noreferrer nofollow" to all links.
    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
      const targetIndex = tokens[idx].attrIndex('target')
      if (targetIndex < 0) {
        tokens[idx].attrPush(['target', '_blank'])
      }
      const relIndex = tokens[idx].attrIndex('rel')
      if (relIndex < 0) {
        tokens[idx].attrPush(['rel', 'noopener noreferrer nofollow'])
      }

      // Prevent container handlers from being called when clicking on a link.
      const onClickIndex = tokens[idx].attrIndex('onmousedown')
      if (onClickIndex < 0) {
        tokens[idx].attrPush([
          'onmousedown',
          '(function(event) { event.stopImmediatePropagation(); })(event)',
        ])
      }
      return self.renderToken(tokens, idx, options)
    }
  }

  if (enableImages) {
    const renderImage = md.renderer.rules.image
    md.renderer.rules.image = function (tokens, idx, options, env, self) {
      // Only Baserow references resolved above render; external images are placeholders.
      const src = tokens[idx].attrGet('src')
      if (!resolvedUrls.has(src)) {
        const alt = md.utils.escapeHtml(
          self.renderInlineAsText(tokens[idx].children || [], options, env)
        )
        return alt ? `${IMAGE_PLACEHOLDER} ${alt}` : IMAGE_PLACEHOLDER
      }
      return renderImage(tokens, idx, options, env, self)
    }
  } else {
    md.inline.ruler.at('image', literalImage)
  }

  // mentions
  md.use(parseMention(workspaceUsers || [], loggedUserId))

  return renderImagePlaceholders(md.render(content))
}
