import { useNuxtApp } from '#app'

import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'

// The errors of a template that changed since the list was loaded, with the
// locale keys of their toast: it was reviewed, edited, blocked or deleted
// meanwhile.
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
// An unlist that finds the template rejected found it unlisted meanwhile.
const UNLIST_CHANGED_ERRORS = {
  ERROR_TEMPLATE_ALREADY_REJECTED: {
    title: 'templatesAdmin.alreadyUnlistedTitle',
    message: 'templatesAdmin.alreadyUnlistedDescription',
  },
}

// Unlisting is a reject of a listed template.
const SERVICE_METHODS = {
  approve: 'approve',
  reject: 'reject',
  unlist: 'reject',
}

/**
 * Whether rejecting the template takes it out of the listing: it's listed, and
 * not as an edit in review, whose reject leaves the approved version listed.
 */
export function rejectUnlists(template) {
  return Boolean(template.listed) && template.state !== 'in_review'
}

/**
 * Reviews the templates of the admin page.
 */
export function useTemplateReview() {
  const { $client, $i18n } = useNuxtApp()
  const service = TemplatesAdminService($client)

  /**
   * Approves or rejects the revision, state and listing that the admin sees,
   * which the server refuses when the template changed since, with a toast. In
   * both cases the list must be refreshed, which moves the template to the tab
   * of its new state. Other errors are thrown.
   *
   * @param {object} template The row of the template, as the admin sees it.
   * @param {string} action `approve`, `reject` or `unlist`.
   * @param {...any} args The arguments of the action, like the reason.
   */
  async function review(template, action, ...args) {
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
      error.handler.notifyIf('template', {
        title: $i18n.t(changed.title, { name }),
        message: $i18n.t(changed.message),
      })
    }
  }

  return { review }
}
