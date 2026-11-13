const transformNode = (node) => ({
  ...node,
  identifier: node.identifier || node.name,
  description: node.description || null,
  icon: node.icon || 'iconoir-database',
  highlightingColor: null,
  examples: null,
  order: node.order || null,
  signature: null,
  nodes: node.nodes
    ? node.nodes.map(transformNode).sort((a, b) => a.order - b.order)
    : [],
})

/**
 * Processes a list of data providers to extract and transform their nodes
 * into a structure compatible with the FormulaInputField component. It also
 * filters out any top-level nodes that do not have any nested nodes.
 *
 * @param {Array} dataProviders - An array of data provider instances.
 * @param {Object} applicationContext - The context required by the data providers' getNodes method.
 * @returns {Array} An array of filtered and transformed data nodes.
 */
export const getDataNodesFromDataProvider = (
  dataProviders,
  applicationContext
) => {
  if (!dataProviders) {
    return []
  }

  return dataProviders
    .map((dataProvider) => {
      const providerNodes = dataProvider.getNodes(applicationContext)

      // Recursively transform provider nodes to match FormulaInputField's expected structure
      // Ensure providerNodes is an array before processing
      if (Array.isArray(providerNodes)) {
        return providerNodes
          .map(transformNode)
          .sort((a, b) => a.order - b.order)
      } else {
        // If it's a single object, transform and add it
        return transformNode(providerNodes)
      }
    })
    .flat()
    .filter((node) => node.nodes && node.nodes.length > 0)
}

/**
 * Returns the example value of the data node at the given data explorer path,
 * for instance `previous_node.12.0.field_34`, by asking the data provider the
 * path belongs to. Meant to be given as `getValue` to the data entry of a
 * formula input's nodes hierarchy, so that the explorer shows the values.
 *
 * @param {Array} dataProviders - The data providers offered by the input.
 * @param {Object} applicationContext - The context the providers read from.
 * @param {String} path - The path of the data node in the explorer.
 * @returns The example value, or `undefined` when there is none.
 */
export const getSampleValueFromDataProviders = (
  dataProviders,
  applicationContext,
  path
) => {
  const [providerType, ...rest] = path.split('.')
  const dataProvider = (dataProviders || []).find(
    (provider) => provider.type === providerType
  )
  return dataProvider?.getSampleValue(applicationContext, rest)
}
