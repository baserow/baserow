const ACTION_FIELD_LABELS = {
  name: 'agent.actionName',
  description: 'agent.actionDescription',
  inputs: 'agent.actionInputs',
  service: 'agent.actionConfiguration',
  type: 'agent.actionFieldType',
  integration_id: 'agent.actionFieldIntegration',
}

export const ACTION_ERROR_LABELS = {
  required: 'agent.actionErrorRequired',
  invalid: 'agent.actionErrorInvalid',
  unavailable: 'agent.actionErrorUnavailable',
}

export const ACTION_INPUT_TYPE_LABELS = {
  string: 'agent.actionInputTypeString',
  email: 'agent.actionInputTypeEmail',
  number: 'agent.actionInputTypeNumber',
  boolean: 'agent.actionInputTypeBoolean',
}

/**
 * Names a field of an action as its editor does: the label its service form
 * shows, else the label of what every action has, else the field itself.
 *
 * @param {object} registry The application registry.
 * @param {string} type The action's type, which is its service type.
 * @param {string} field The field name, as the backend reports it.
 * @param {Function} t The translate function.
 * @returns {string} The label.
 */
export function actionFieldLabel(registry, type, field, t) {
  const serviceLabels = registry.exists('toolPresentation', type)
    ? registry.get('toolPresentation', type).fieldLabels
    : {}
  const label = serviceLabels[field] || ACTION_FIELD_LABELS[field]
  return label ? t(label) : field
}
