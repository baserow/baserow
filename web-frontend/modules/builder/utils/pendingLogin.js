import { useCookie } from '#imports'
import { uuid } from '@baserow/modules/core/utils/string'
import { getCookieName } from '@baserow/modules/core/utils/cookie'
import { getLoginCompletionCookieName } from '@baserow/modules/core/utils/userSourceCallback'
import { populateWorkflowAction } from '@baserow/modules/builder/store/builderWorkflowAction'

const storageKey = 'baserow.builder.pendingLogin'

/** Preserve the initiating form's event across an external SSO navigation. */
export const rememberPendingLogin = ({
  builder,
  page,
  element,
  userSource,
  workflowActions,
  recordIndexPath,
}) => {
  const attemptId = uuid()
  try {
    window.sessionStorage.setItem(
      storageKey,
      JSON.stringify({
        attemptId,
        builderId: builder.id,
        pageId: page.id,
        userSourceUid: userSource.uid,
        element,
        workflowActions,
        recordIndexPath,
      })
    )
    return attemptId
  } catch {
    // Storage can be disabled. Authentication must still work in that case.
  }
}

export const clearPendingLogin = () => {
  try {
    window.sessionStorage.removeItem(storageKey)
  } catch {
    // Storage can be disabled.
  }
}

/** Resume once, after authentication, even if the login form is now hidden. */
export const resumePendingLogin = async (app, applicationContext) => {
  let pending
  try {
    const value = window.sessionStorage.getItem(storageKey)
    clearPendingLogin()
    pending = JSON.parse(value)
  } catch {
    return
  }

  const cookieName = getLoginCompletionCookieName(pending?.attemptId)
  const completed =
    cookieName &&
    app.runWithContext(() => {
      const cookie = useCookie(getCookieName(app.$config, cookieName), {
        path: '/',
      })
      const received = cookie.value === 1 || cookie.value === '1'
      cookie.value = null
      return received
    })
  const { builder, page, mode } = applicationContext
  if (
    !pending ||
    !completed ||
    mode === 'editing' ||
    pending.builderId !== builder.id ||
    pending.pageId !== page.id ||
    !app.$store.getters['userSourceUser/isAuthenticated'](builder) ||
    pending.userSourceUid !==
      app.$store.getters['userSourceUser/getUser'](builder).user_source_uid
  ) {
    return
  }

  // Published responses may omit logged-out-only forms and their actions after
  // authentication. Use the initiating form's configuration, not its mounted UI.
  const event = app.$registry
    .get('element', pending.element.type)
    .getEventByName(pending.element, 'after_login')
  return await event.fire({
    workflowActions: pending.workflowActions.map(populateWorkflowAction),
    applicationContext: {
      ...applicationContext,
      element: pending.element,
      recordIndexPath: pending.recordIndexPath,
    },
  })
}
