import { useNuxtApp } from '#app'

import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'

// The toast for a template that changed since the list was loaded.
const CHANGED = {
  title: 'templatesAdmin.changedTitle',
  message: 'templatesAdmin.changedDescription',
}
const CHANGED_ERRORS = {
  ERROR_TEMPLATE_ALREADY_APPROVED: {
    title: 'templatesAdmin.alreadyApprovedTitle',
    message: 'templatesAdmin.alreadyApprovedDescription',
  },
  ERROR_TEMPLATE_ALREADY_REJECTED: {
    title: 'templatesAdmin.alreadyRejectedTitle',
    message: 'templatesAdmin.alreadyRejectedDescription',
  },
  ERROR_TEMPLATE_UPDATED: CHANGED,
  ERROR_TEMPLATE_NOT_REVIEWABLE: CHANGED,
  ERROR_TEMPLATE_BLOCKED: CHANGED,
  ERROR_TEMPLATE_DOES_NOT_EXIST: CHANGED,
}
// An unlist that finds it rejected: most likely another admin unlisted it.
const UNLIST_CHANGED_ERRORS = {
  ERROR_TEMPLATE_ALREADY_REJECTED: {
    title: 'templatesAdmin.alreadyUnlistedTitle',
    message: 'templatesAdmin.alreadyUnlistedDescription',
  },
}

// The preview's workspace can't be opened: made private, deleted or updated.
const CONTENT_CHANGED_ERRORS = [
  'ERROR_USER_NOT_IN_GROUP',
  'ERROR_GROUP_DOES_NOT_EXIST',
]

// Unlisting is a reject of a listed template.
const SERVICE_METHODS = {
  approve: 'approve',
  reject: 'reject',
  unlist: 'reject',
}

/**
 * Reviews the templates of the admin page.
 */
export function useTemplateReview() {
  const { $client, $i18n } = useNuxtApp()
  const service = TemplatesAdminService($client)

  /**
   * Tells the admin that the template changed since the list was loaded.
   *
   * @param {object} error The error of the request, with its handler.
   * @param {object} toast The locale keys of the title and message.
   * @param {string} name The name of the template.
   */
  function notifyChanged(error, toast, name) {
    error.handler.notifyIf('template', {
      title: $i18n.t(toast.title, { name }),
      message: $i18n.t(toast.message),
    })
  }

  /**
   * Approves, rejects or unlists the template as the admin saw it. If it
   * changed since, the admin gets a toast; other errors are thrown.
   *
   * @param {object} template The row of the template, as the admin sees it.
   * @param {string} action `approve`, `reject` or `unlist`.
   * @param {...any} args The arguments of the action, like the reason.
   */
  async function decide(template, action, ...args) {
    const { id, revision_id: revisionId, name, state, listed } = template
    try {
      await service[SERVICE_METHODS[action]](
        id,
        revisionId,
        ...args,
        state,
        listed
      )
    } catch (error) {
      const code = error.handler?.code
      const changed =
        (action === 'unlist' && UNLIST_CHANGED_ERRORS[code]) ||
        CHANGED_ERRORS[code]
      if (!changed) {
        throw error
      }
      notifyChanged(error, changed, name)
    }
  }

  /**
   * Handles an error loading the content of the template in its preview: when
   * the admin can't open it anymore, it changed since the list was loaded.
   *
   * @param {object} template The row of the template.
   * @param {object} error The error of the request.
   * @returns {boolean} Whether it changed, which the admin was told.
   */
  function contentFailed(template, error) {
    if (!CONTENT_CHANGED_ERRORS.includes(error.handler?.code)) {
      return false
    }
    notifyChanged(error, CHANGED, template.name)
    return true
  }

  return { decide, contentFailed }
}
