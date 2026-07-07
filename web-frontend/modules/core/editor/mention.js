import { Mention as TiptapMention } from '@tiptap/extension-mention'
import regexp from 'markdown-it-regexp'

import { escapeHtml } from '@baserow/modules/core/utils/string'

const USER_ID_REGEXP = /@(\d+)/

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

export const Mention = TiptapMention.extend({
  addOptions() {
    return {
      ...this.parent?.(),
      users: [],
      loggedUserId: null,
    }
  },
  addStorage() {
    return {
      markdown: {
        serialize(state, node) {
          const userId = node.attrs.id
          if (userId) {
            state.write(`@${userId}`)
          }
        },
        parse: {
          setup(markdownit) {
            markdownit.use(
              parseMention(this.options.users, this.options.loggedUserId)
            )
          },
        },
      },
    }
  },
})
