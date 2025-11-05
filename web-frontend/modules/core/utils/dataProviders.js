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
  const dataNodes = []
  if (!dataProviders) {
    return []
  }

  for (const dataProvider of dataProviders) {
    if (dataProvider && typeof dataProvider.getNodes === 'function') {
      const providerNodes = dataProvider.getNodes(applicationContext)
      if (providerNodes) {
        // Recursively transform provider nodes to match FormulaInputField's expected structure
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
          nodes: node.nodes ? node.nodes.map(transformNode) : [],
        })

        // Ensure providerNodes is an array before processing
        if (Array.isArray(providerNodes)) {
          dataNodes.push(...providerNodes.map(transformNode))
        } else if (typeof providerNodes === 'object') {
          // If it's a single object, transform and add it
          dataNodes.push(transformNode(providerNodes))
        }
      }
    }
  }

  // Filter out first-level data nodes that have empty nodes arrays
  return dataNodes.filter((node) => node.nodes && node.nodes.length > 0)
}
