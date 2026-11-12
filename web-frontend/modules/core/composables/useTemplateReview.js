import { useNuxtApp } from '#app'

import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'

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
const UNLIST_CHANGED_ERRORS = {
  ERROR_TEMPLATE_ALREADY_REJECTED: {
    title: 'templatesAdmin.alreadyUnlistedTitle',
    message: 'templatesAdmin.alreadyUnlistedDescription',
  },
}

const CONTENT_CHANGED_ERRORS = [
  'ERROR_USER_NOT_IN_GROUP',
  'ERROR_GROUP_DOES_NOT_EXIST',
]

const SERVICE_METHODS = {
  approve: 'approve',
  reject: 'reject',
  unlist: 'reject',
}
const MODERATIONS = ['block', 'unblock']

export function useTemplateReview() {
  const { $client, $i18n } = useNuxtApp()
  const service = TemplatesAdminService($client)

  function notifyChanged(error, toast, name) {
    error.handler.notifyIf('template', {
      title: $i18n.t(toast.title, { name }),
      message: $i18n.t(toast.message),
    })
  }

  async function decide(template, action, ...args) {
    const {
      id,
      revision_id: revisionId,
      name,
      state,
      listed,
      reviewed_on: reviewedOn,
    } = template
    try {
      if (MODERATIONS.includes(action)) {
        const { data } = await service[action](id, ...args)
        return data
      }
      await service[SERVICE_METHODS[action]](
        id,
        revisionId,
        ...args,
        state,
        listed,
        reviewedOn
      )
      return true
    } catch (error) {
      const code = error.handler?.code
      const changed =
        (action === 'unlist' && UNLIST_CHANGED_ERRORS[code]) ||
        CHANGED_ERRORS[code]
      if (!changed) {
        throw error
      }
      notifyChanged(error, changed, name)
      return false
    }
  }

  function contentFailed(template, error) {
    if (!CONTENT_CHANGED_ERRORS.includes(error.handler?.code)) {
      return false
    }
    notifyChanged(error, CHANGED, template.name)
    return true
  }

  return { decide, contentFailed }
}
