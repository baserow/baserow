/**
 * Whether a user may rename, delete or stop a conversation. A shared one is
 * the Agent's to manage, a private one only its owner's: the people asked to
 * approve in it only read it.
 *
 * @param {object} conversation The conversation, with its `owner` or null.
 * @param {number} userId The user's id.
 * @param {boolean} canUpdateAgent Whether the user may update the Agent.
 * @returns {boolean} Whether the user manages the conversation.
 */
export function managesConversation(conversation, userId, canUpdateAgent) {
  if (conversation.shared) return canUpdateAgent
  return Boolean(conversation.local) || conversation.owner?.id === userId
}
