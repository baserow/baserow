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

const prepareMarkdownForPreview = (value) => {
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
  const md = new Markdown({ html: false })

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
    md.renderer.rules.image = function (tokens, idx, options, env, self) {
      // Show only the first image in the preview.
      const style = tokens[idx].attrIndex('style')
      if (style < 0) {
        tokens[idx].attrPush(['style', 'display: block;'])
      }
      return self.renderToken(tokens, idx, options)
    }
  } else {
    md.disable('image')
  }

  // mentions
  md.use(parseMention(workspaceUsers || [], loggedUserId))

  return md.render(prepareMarkdownForPreview(value || ''))
}
