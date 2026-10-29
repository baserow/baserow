/**
 * Whether the template is one of the user's own templates. Only those carry a
 * state, see the template serializers.
 */
export function isOwnTemplate(template) {
  return template.state !== null && template.state !== undefined
}

/**
 * Tells the author that the template was updated since it was shown, so it stays
 * private until they checked the update.
 */
export function notifyTemplateUpdated(error, t) {
  error.handler.notifyIf('template', {
    title: t('clientHandler.templateUpdatedTitle'),
    message: t('makeTemplatePublicModal.updated'),
  })
}
