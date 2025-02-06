import _ from 'lodash'

/**
 * Responsible for returning the default value for a parameter,
 * based on the parameter's type.
 *
 * @param type The parameter's type (e.g. `text` or `numeric`).
 * @returns {String} The default value.
 */
export function defaultValueForParameterType(type) {
  return type === 'numeric' ? 1 : 'test'
}

// The regex for query parameters. This is used to validate query parameter names.
// This needs to match QUERY_PARAM_EXACT_MATCH_REGEX from backend.
export const QUERY_PARAM_REGEX = /^([A-Za-z][A-Za-z0-9_-]*)$/g

/**
 * Responsible for detecting if a navigable record's path parameters have diverged
 * from the destination page's path parameters. This can happen if a record
 * points to a page, and then the page's parameters are altered.
 *
 * @param {Object} navigationObject - An `element` or `workflowAction` object
 *  which points to navigation data. In the case of an `element` this could be
 *  a button, and in the case of a `workflowAction` this could be an "open page"
 *  workflow action type.
 * @param {Array} pages - An array of "visible" pages in the application.
 * @returns {Boolean} Whether this navigable object has parameters in error.
 */
export function pathParametersInError(navigationObject, pages) {
  if (
    navigationObject.navigation_type === 'page' &&
    !isNaN(navigationObject.navigate_to_page_id)
  ) {
    const destinationPage = pages.find(
      ({ id }) => id === navigationObject.navigate_to_page_id
    )

    if (destinationPage) {
      const destinationPageParams = destinationPage.path_params || []
      const pageParams = navigationObject.page_parameters || []

      const destinationPageParamNames = destinationPageParams.map(
        ({ name }) => name
      )
      const pageParamNames = pageParams.map(({ name }) => name)

      if (!_.isEqual(destinationPageParamNames, pageParamNames)) {
        return true
      }
    }
  }
  return false
}

/**
 * Given dispatch refinement records, this function is responsible for generating
 * the URLSearchParams that data source and workflow action dispatches will use.
 * @param range The range of records to retrieve.
 * @param filters The adhoc filters to apply to the dispatch results.
 * @param sortings The adhoc sortings to apply to the dispatch results.
 * @param search The search query to apply to the dispatch results.
 * @param searchMode The search mode to apply to the dispatch results.
 * @returns {URLSearchParams} The URLSearchParams object to use in dispatches.
 */
export function prepareDispatchParams({
  range,
  filters = {},
  sortings = null,
  search = '',
  searchMode = '',
}) {
  const params = new URLSearchParams()
  if (range) {
    params.append('offset', range[0])
    params.append('count', range[1])
  }

  Object.keys(filters).forEach((key) => {
    filters[key].forEach((value) => {
      params.append(key, value)
    })
  })

  if (sortings || sortings === '') {
    params.append('order_by', sortings)
  }

  if (search) {
    params.append('search_query', search)
    if (searchMode) {
      params.append('search_mode', searchMode)
    }
  }

  return params
}
