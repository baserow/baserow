import { mergeAttributes } from '@tiptap/core'
import { Mention as TiptapMention } from '@tiptap/extension-mention'

import { escapeHtml } from '@baserow/modules/core/utils/string'

// `extract_mentioned_user_ids` in rich_text_utils.py follows the same rule.
const USER_ID_REGEXP = /@(\d+)(?![A-Za-z0-9])/
const LEADING_MENTION_REGEXP = /^@(\d+)(?![A-Za-z0-9])/
const MENTION_PREFIX_CHARACTER_REGEXP = /[\w.%+-]/

// The editor reads a mention again after an escaped character or another
// mention, so only plain text before it keeps it literal.
const isLiteralMention = (source, position) => {
  const before = position - 1
  if (before < 0 || !MENTION_PREFIX_CHARACTER_REGEXP.test(source[before])) {
    return false
  }
  let backslashes = before
  while (backslashes > 0 && source[backslashes - 1] === '\\') backslashes--
  if ((before - backslashes) % 2) {
    return false
  }
  let digits = before
  while (digits >= 0 && /[0-9]/.test(source[digits])) digits--
  return digits < 0 || source[digits] !== '@'
}

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

export const parseMention =
  (users, loggedUserId = null) =>
  (markdownIt) => {
    const ruleName = 'baserow-mention'

    markdownIt.inline.ruler.push(ruleName, (state, silent) => {
      if (state.src.charCodeAt(state.pos) !== 0x40) {
        return false
      }

      if (isLiteralMention(state.src, state.pos)) {
        return false
      }

      const match = state.src.slice(state.pos).match(LEADING_MENTION_REGEXP)
      if (!match) {
        return false
      }

      state.pos += match[0].length
      if (silent) {
        return true
      }

      const token = state.push(ruleName, '', 0)
      token.meta = { match }
      return true
    })

    markdownIt.renderer.rules[ruleName] = (tokens, index) => {
      const { match } = tokens[index].meta
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
    }
  }

export const createMention = ({
  users = [],
  loggedUserId = null,
  suggestion = undefined,
} = {}) => {
  const getUsers = () => (typeof users === 'function' ? users() : users) || []
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
          const mention = source.slice(mentionIndex).match(USER_ID_REGEXP)
          return {
            type: 'mention',
            raw: source.slice(0, mentionIndex + mention[0].length),
          }
        }
        const match = source.match(LEADING_MENTION_REGEXP)
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
      const user = getUsers().find(
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
      const user = getUsers().find(({ user_id: id }) => id === userId)
      const label = user?.name ?? node.attrs.label ?? node.attrs.id
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
