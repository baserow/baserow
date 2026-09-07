import { Extension } from '@tiptap/core'
import { Blockquote } from '@tiptap/extension-blockquote'
import { Bold } from '@tiptap/extension-bold'
import { BulletList as BaseBulletList } from '@tiptap/extension-bullet-list'
import { Code as BaseCode } from '@tiptap/extension-code'
import { CodeBlock as BaseCodeBlock } from '@tiptap/extension-code-block'
import { Document } from '@tiptap/extension-document'
import { Dropcursor } from '@tiptap/extension-dropcursor'
import { Gapcursor } from '@tiptap/extension-gapcursor'
import { HardBreak } from '@tiptap/extension-hard-break'
import { Heading as BaseHeading } from '@tiptap/extension-heading'
import { History } from '@tiptap/extension-history'
import { HorizontalRule } from '@tiptap/extension-horizontal-rule'
import { Italic } from '@tiptap/extension-italic'
import { isAllowedUri, Link as BaseLink } from '@tiptap/extension-link'
import { ListItem as BaseListItem } from '@tiptap/extension-list-item'
import { OrderedList } from '@tiptap/extension-ordered-list'
import { Paragraph } from '@tiptap/extension-paragraph'
import { Strike as BaseStrike } from '@tiptap/extension-strike'
import { Subscript } from '@tiptap/extension-subscript'
import { Superscript } from '@tiptap/extension-superscript'
import { TaskItem } from '@tiptap/extension-task-item'
import { TaskList } from '@tiptap/extension-task-list'
import { Text } from '@tiptap/extension-text'
import { Underline } from '@tiptap/extension-underline'
import { Markdown } from '@tiptap/markdown'
import { Slice } from '@tiptap/pm/model'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Marked } from 'marked'

import { ScalableImage } from '@baserow/modules/core/editor/image'
import { rememberRichTextEditorClipboard } from '@baserow/modules/core/editor/richTextClipboard'
import {
  decodeInlineCodeText,
  LegacyNumericHtmlEntity,
  LiteralInlineMarkdownHtml,
  LiteralMarkdownHtml,
  MarkdownDocumentCompatibility,
  MarkdownInputCapture,
} from '@baserow/modules/core/editor/markdownCompatibility'

export const MARKDOWN_OPTIONS = {
  breaks: true,
  gfm: true,
}

export const createMarkedInstance = () => new Marked()

const HEADING_LEVELS = [1, 2, 3]
const LINK_PROTOCOLS = [
  { scheme: 'ftp' },
  { scheme: 'mailto', optionalSlashes: true },
  { scheme: 'tel', optionalSlashes: true },
]

const Heading = BaseHeading.extend({
  parseMarkdown(token, helpers) {
    const content = helpers.parseInline(token.tokens ?? [])
    return HEADING_LEVELS.includes(token.depth)
      ? helpers.createNode('heading', { level: token.depth }, content)
      : helpers.createNode('paragraph', undefined, content)
  },
  renderMarkdown(node, helpers) {
    const level = HEADING_LEVELS.includes(node.attrs?.level)
      ? node.attrs.level
      : HEADING_LEVELS[0]
    return `${'#'.repeat(level)} ${helpers.renderChildren(node.content ?? [])}`
  },
})

const Strike = BaseStrike.extend({
  parseMarkdown(token, helpers) {
    return token.raw?.startsWith('~~')
      ? helpers.applyMark('strike', helpers.parseInline(token.tokens ?? []))
      : helpers.createTextNode(token.raw ?? token.text ?? '')
  },
})

const decodeMarkdownEscapes = (text) =>
  text.replace(/\\([!"#$%&'()*+,\-./:;<=>?@[\]\\^_`{|}~])/g, '$1')

const Link = BaseLink.extend({
  parseMarkdown(token, helpers) {
    const raw = token.raw ?? ''
    const isExplicitLink = raw.startsWith('[') || raw.startsWith('<')
    const isSafeLink = isAllowedUri(token.href, LINK_PROTOCOLS)

    if (!isExplicitLink || !isSafeLink) {
      return helpers.createTextNode(decodeMarkdownEscapes(raw))
    }

    return helpers.applyMark('link', helpers.parseInline(token.tokens ?? []), {
      href: token.href,
      title: token.title ?? null,
    })
  },
})

const Code = BaseCode.extend({
  parseMarkdown(token, helpers) {
    return helpers.applyMark('code', [
      helpers.createTextNode(decodeInlineCodeText(token.text ?? '')),
    ])
  },
  renderMarkdown(node, helpers) {
    const content = helpers.renderChildren(node.content ?? [])
    const delimiter = node.attrs?.markdownDelimiter ?? '`'
    const padding = node.attrs?.markdownPadding ? ' ' : ''
    return `${delimiter}${padding}${content}${padding}${delimiter}`
  },
})

const CodeBlock = BaseCodeBlock.extend({
  renderMarkdown(node, helpers) {
    const content = helpers.renderChildren(node.content ?? [])
    const longestBacktickRun = Math.max(
      2,
      ...(content.match(/`+/g) ?? []).map(({ length }) => length)
    )
    const fence = '`'.repeat(longestBacktickRun + 1)
    const language = node.attrs?.language ?? ''
    return `${fence}${language}\n${content}\n${fence}`
  },
})

const ListItem = BaseListItem.extend({
  renderMarkdown(node, helpers, context) {
    const emptyParagraphMarker = '\uE002'
    const children = node.content ?? []
    if (children.length === 0) return ''

    const [first, ...rest] = children
    const normalizedFirst =
      first?.type === 'paragraph' && !first.content?.length
        ? {
            ...first,
            content: [{ type: 'text', text: emptyParagraphMarker }],
          }
        : first

    let marker = '- '
    if (context.parentType === 'orderedList') {
      const start = context.meta?.parentAttrs?.start || 1
      const num = start + (context.index || 0)
      marker = `${num}. `
    }

    const mainContent = helpers.renderChildren([normalizedFirst])
    let output = `${marker}${mainContent}`

    for (let i = 0; i < rest.length; i++) {
      const child = rest[i]
      const rendered =
        helpers.renderChild(child, i + 1) ?? helpers.renderChildren([child])
      if (rendered == null) continue
      const indented = rendered
        .split('\n')
        .map((line) => helpers.indent(line))
        .join('\n')
      const separator = child.type === 'paragraph' ? '\n\n' : '\n'
      output += `${separator}${indented}`
    }

    return output.replace(emptyParagraphMarker, '&nbsp;')
  },
})

const BulletList = BaseBulletList.extend({
  renderMarkdown(node, helpers, context) {
    const rendered = BaseBulletList.config.renderMarkdown(
      node,
      helpers,
      context
    )
    // Marked merges adjacent same-marker lists; runs get alternating markers.
    const marker = node.attrs?.markdownMarker ?? '-'
    return marker === '-'
      ? rendered
      : rendered.replace(/(^|\n)- /g, `$1${marker} `)
  },
})

export function parseMarkdownClipboard(editor, text, plainText) {
  if (plainText) {
    return null
  }

  const document = editor.schema.nodeFromJSON(editor.markdown.parse(text))
  return Slice.maxOpen(document.content)
}

export function serializeMarkdownClipboard(editor, slice) {
  return editor.markdown.serialize({
    type: 'doc',
    content: slice.content.toJSON(),
  })
}

const MarkdownClipboard = Extension.create({
  name: 'markdownClipboard',
  priority: 1000,
  addProseMirrorPlugins() {
    const rememberCopiedSelection = (view) => {
      if (!view.state.selection.empty) {
        rememberRichTextEditorClipboard(
          serializeMarkdownClipboard(
            this.editor,
            view.state.selection.content()
          )
        )
      }
      return false
    }
    return [
      new Plugin({
        key: new PluginKey('markdownClipboard'),
        props: {
          handleDOMEvents: {
            copy: rememberCopiedSelection,
            cut: rememberCopiedSelection,
          },
          clipboardTextParser: (text, _context, plainText) =>
            parseMarkdownClipboard(this.editor, text, plainText),
          clipboardTextSerializer: (slice) =>
            serializeMarkdownClipboard(this.editor, slice),
        },
      }),
    ]
  },
})

export const createRichTextContentExtensions = ({
  openLinksOnClick = false,
  enableImages = false,
} = {}) => {
  const extensions = [
    Document,
    Paragraph,
    Text,
    HardBreak,
    Heading.configure({ levels: HEADING_LEVELS }),
    ListItem,
    OrderedList,
    BulletList,
    CodeBlock,
    Blockquote,
    HorizontalRule,
    TaskItem,
    TaskList,
    Bold,
    Italic,
    Strike,
    Code,
    Underline,
    Subscript,
    Superscript,
    Link.configure({
      protocols: LINK_PROTOCOLS,
      autolink: false,
      openOnClick: openLinksOnClick,
    }),
    LiteralMarkdownHtml,
    LiteralInlineMarkdownHtml,
    LegacyNumericHtmlEntity,
  ]

  if (enableImages) {
    extensions.push(ScalableImage)
  }

  return extensions
}

export const createRichTextEditorExtensions = (options = {}) => {
  const extensions = [
    ...createRichTextContentExtensions(options),
    MarkdownInputCapture,
    Markdown.configure({
      marked: createMarkedInstance(),
      markedOptions: MARKDOWN_OPTIONS,
    }),
    MarkdownDocumentCompatibility,
    MarkdownClipboard,
    History,
  ]

  extensions.push(Dropcursor, Gapcursor)

  return extensions
}

export const createPlainTextEditorExtensions = () => [
  Document,
  Paragraph,
  Text,
  HardBreak,
]
