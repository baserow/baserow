const transformNode = (node) => ({
  name: node.name,
  type: node.type === 'array' ? 'array' : 'data',
  identifier: node.identifier || node.name,
  description: node.description || null,
  icon: node.icon || 'iconoir-database',
  highlightingColor: null,
  example: null,
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
