export default (client, baseUrl, isPaginated = true) => {
  return {
    /**
     * Additionally options that the CrudTable component can use to adjust how your
     * requests are made.
     */
    options: { isPaginated, baseUrl, urlParams: {} },
    /**
     * Fetch data required by the CrudTable component.
     * All parameters are optional.
     * @param baseUrl The base url to use for the request.
     * @param page The page number to fetch.
     * @param searchQuery The search query to filter the results by.
     * @param sorts An array of objects containing the key and direction to sort by.
     * @param filters An object containing the keys and values to filter by.
     * @param options Any additional options that might be passed to the fetch function.
     * @returns {*}
     */
    fetch(baseUrl, page, searchQuery, sorts, filters, options) {
      if (typeof baseUrl === 'function') {
        baseUrl = baseUrl(options.urlParams)
      }

      const params = Object.assign({}, filters)

      if (page) {
        params.page = page
      }

      if (searchQuery) {
        params.search = searchQuery
      }
      if (sorts.length > 0) {
        params.sorts = sorts
          .map((s) => {
            const direction = s.direction === 'asc' ? '-' : '+'
            return `${direction}${s.key}`
          })
          .join(',')
      }

      return client.get(baseUrl, { params })
    },
    /**
     * Fetch items by a list of IDs using the `ids` query parameter supported
     * by the APIListingView.
     * @param baseUrl The base url to use for the request.
     * @param ids An array of numeric IDs to filter by.
     * @returns {*}
     */
    fetchByIds(baseUrl, ids) {
      return client.get(baseUrl, { params: { ids: ids.join(',') } })
    },
  }
}
