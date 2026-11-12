import { inject, reactive } from 'vue'
import { useStore } from 'vuex'

import { useTemplateReview } from '@baserow/modules/core/composables/useTemplateReview'
import { notifyIf } from '@baserow/modules/core/utils/error'

export const TEMPLATE_MODERATION = Symbol('templateModeration')

/**
 * Blocks, changes the block reason of and unblocks user templates, one request
 * per template at a time. The component that shows template previews provides it
 * to them, so that it completes a request also when the preview was closed since.
 *
 * @param {Function} moderated Called with the template once a request ended, also
 *   when the template changed since. The next request for the template waits for
 *   the promise it returns.
 * @param {object} options
 * @param {boolean} options.showsCounts The provider shows the admin counts, which
 *   are then also loaded when they couldn't be loaded before.
 */
export function useTemplateModeration(moderated, { showsCounts = false } = {}) {
  const store = useStore()
  const { decide } = useTemplateReview()
  const parent = inject(TEMPLATE_MODERATION, null)
  const pending = parent?.pending ?? reactive(new Set())

  async function refresh(template) {
    await moderated(template)
    if (parent) {
      await parent.refresh(template)
    } else if (showsCounts || store.getters['templatesAdmin/counts'] !== null) {
      store
        .dispatch('templatesAdmin/fetchCounts', { force: true })
        .catch((error) => notifyIf(error, 'template'))
    }
  }

  async function moderate(template, action, ...args) {
    const { id } = template
    if (pending.has(id)) {
      return false
    }
    pending.add(id)
    try {
      const row = await decide(template, action, ...args)
      await refresh(template)
      return row
    } finally {
      pending.delete(id)
    }
  }

  return {
    moderate,
    isModerating: (id) => pending.has(id),
    pending,
    refresh,
  }
}
