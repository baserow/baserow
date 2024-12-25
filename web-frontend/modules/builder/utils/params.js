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

/**
 * Responsible for detecting if an element's path parameters have diverged
 * from the destination page's path parameters. This can happen if an element
 * points to a page, and then the page's parameters are altered.
 *
 * @param {Object} element The element's properties we'll validate.
 * @param {Object} pages Page of this application.
 * @returns {Boolean} Whether this resolvedUrl is external.
 */
export function pathParametersInError(element, pages) {
  if (
    element.navigation_type === 'page' &&
    !isNaN(element.navigate_to_page_id)
  ) {
    const destinationPage = pages.find(
      ({ id }) => id === element.navigate_to_page_id
    )

    if (destinationPage) {
      const destinationPageParams = destinationPage.path_params || []
      const pageParams = element.page_parameters || []

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
