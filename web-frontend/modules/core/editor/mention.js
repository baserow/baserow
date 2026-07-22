import { mergeAttributes } from '@tiptap/core'
import { Mention as TiptapMention } from '@tiptap/extension-mention'
import regexp from 'markdown-it-regexp'

import { escapeHtml } from '@baserow/modules/core/utils/string'

const USER_ID_REGEXP = /@(\d+)/
const MENTION_PREFIX_CHARACTER_REGEXP = /[\w.%+-]/

const findMentionStart = (source) => {
  const mentionIndex = source.search(USER_ID_REGEXP)
  if (mentionIndex < 0) {
    return -1
  }

  let prefixIndex = mentionIndex
  while (
    prefixIndex > 0 &&
    MENTION_PREFIX_CHARACTER_REGEXP.test(source[prefixIndex - 1])
  ) {
    prefixIndex--
  }
  return prefixIndex
}

export const parseMention = (users, loggedUserId = null) =>
  regexp(USER_ID_REGEXP, (match, utils) => {
    const user = users.find((user) => user.user_id === parseInt(match[1]))
    if (user) {
      let className = 'rich-text-editor__mention'
      if (user.user_id === loggedUserId) {
        className += ' rich-text-editor__mention--current-user'
      }
      const name = escapeHtml(user.name)
      // NOTE: Keep this in sync with the @tiptap/extension-mention
      // https://github.com/ueberdosis/tiptap/blob/main/packages/extension-mention/src/mention.ts
      return `<span class="${className}" data-id="${user.user_id}" data-label="${name}" data-type="mention">@${name}</span>`
    } else {
      return `@${match[1]}`
    }
  })

export const createMention = ({
  users = [],
  loggedUserId = null,
  suggestion = undefined,
} = {}) => {
  const extension = TiptapMention.extend({
    markdownTokenName: 'mention',
    markdownTokenizer: {
      name: 'mention',
      level: 'inline',
      start(source) {
        return findMentionStart(source)
      },
      tokenize(source) {
        const mentionIndex = source.search(USER_ID_REGEXP)
        if (mentionIndex > 0 && findMentionStart(source) === 0) {
          return {
            type: 'mention',
            raw: source.slice(0, mentionIndex),
          }
        }
        const match = source.match(/^@(\d+)/)
        if (!match) {
          return undefined
        }
        return {
          type: 'mention',
          raw: match[0],
          userId: match[1],
        }
      },
    },
    parseMarkdown(token, helpers) {
      const user = users.find(
        ({ user_id: userId }) => userId === parseInt(token.userId)
      )
      if (!user) {
        return helpers.createTextNode(token.raw)
      }
      return helpers.createNode('mention', {
        id: token.userId,
        label: user.name,
      })
    },
    renderMarkdown(node) {
      return node.attrs?.id ? `@${node.attrs.id}` : ''
    },
  })

  const options = {
    renderHTML: ({ options: mentionOptions, node }) => {
      const userId = parseInt(node.attrs.id)
      const user = users.find(({ user_id: id }) => id === userId)
      const label = node.attrs.label ?? user?.name ?? node.attrs.id
      const classes = ['rich-text-editor__mention']
      if (userId === loggedUserId) {
        classes.push('rich-text-editor__mention--current-user')
      } else if (!user) {
        classes.push('rich-text-editor__mention--user-gone')
      }
      return [
        'span',
        mergeAttributes(mentionOptions.HTMLAttributes, {
          class: classes.join(' '),
        }),
        `@${label}`,
      ]
    },
  }
  if (suggestion !== undefined) {
    options.suggestion = suggestion
  }

  return extension.configure(options)
}
