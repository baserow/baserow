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
