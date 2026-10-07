import {
  PreviousNodeDataProviderType,
  CurrentIterationDataProviderType,
} from '@baserow/modules/automation/dataProviderTypes'

/**
 * A list of all the data providers that can be used to configure automation nodes.
 *
 * @type {String[]}
 */
export const DATA_PROVIDERS_ALLOWED_NODE_ACTIONS = [
  CurrentIterationDataProviderType.getType(),
  PreviousNodeDataProviderType.getType(),
]

/**
 * What an action node does when one of its attempts fails. Mirrors the
 * backend's `AutomationNodeOnFailure` choices.
 */
export const NODE_ON_FAILURE = {
  STOP: 'stop',
  RETRY: 'retry',
}

/**
 * Bounds of a node's retries count, as enforced by the backend's `max_retries`
 * validators. The default comes from the backend with the node.
 */
export const NODE_RETRIES = {
  MIN: 1,
  MAX: 5,
}
