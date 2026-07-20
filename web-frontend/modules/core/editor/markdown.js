import Markdown from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import { MarkdownManager } from '@tiptap/markdown'

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
  preprocessRichTextImages,
  replaceImagesWithPlaceholder,
  stripUnresolvedImageRefs,
} from '@baserow/modules/core/editor/richTextImageUtils'

const previewMarkdownManager = new MarkdownManager({
  extensions: createRichTextContentExtensions(),
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

export const parseMarkdown = (
  value,
  {
    openLinkOnClick = false,
    enableImages = false,
    workspaceUsers = null,
    loggedUserId = null,
  } = {}
) => {
  let content = value || ''

  if (enableImages) {
    content = preprocessRichTextImages(content).content
    content = stripUnresolvedImageRefs(content)
  } else {
    content = replaceImagesWithPlaceholder(content)
  }

  const md = new Markdown({ html: false })

  // task lists
  md.use(taskLists, { label: true, enabled: true })

  // link
  if (!openLinkOnClick) {
    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
      const hrefIndex = tokens[idx].attrIndex('href')
      if (hrefIndex >= 0) {
        tokens[idx].attrs.splice(hrefIndex, 1)
      }
      return self.renderToken(tokens, idx, options)
    }
  } else {
    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
      const targetIndex = tokens[idx].attrIndex('target')
      if (targetIndex < 0) {
        tokens[idx].attrPush(['target', '_blank'])
      }
      const relIndex = tokens[idx].attrIndex('rel')
      if (relIndex < 0) {
        tokens[idx].attrPush(['rel', 'noopener noreferrer nofollow'])
      }

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
    md.renderer.rules.image = function (tokens, idx, options, env, self) {
      const style = tokens[idx].attrIndex('style')
      if (style < 0) {
        tokens[idx].attrPush(['style', 'display: block; max-width: 100%;'])
      }
      return self.renderToken(tokens, idx, options)
    }
  } else {
    md.disable('image')
  }

  // mentions
  md.use(parseMention(workspaceUsers || [], loggedUserId))

  return md.render(prepareMarkdownForPreview(content))
}
