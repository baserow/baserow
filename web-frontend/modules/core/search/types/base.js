export class BaseSearchType {
  constructor(context = {}) {
    this.app = context.app
    this.type = null
    this.name = null
    this.icon = 'iconoir-search'
    this.priority = 10
  }

  /**
   * Builds the URL for navigating to this search result.
   * Must be implemented by subclasses.
   * @param {Object} result - The search result object
   * @param {Object} context - Context containing store reference
   * @returns {string|Object|null} URL string, route object, or null if not navigable
   */
  buildUrl(result, context = null) {
    throw new Error('buildUrl must be implemented by subclass')
  }

  getIcon() {
    return this.icon
  }

  getName() {
    return this.name
  }

  getType() {
    return this.type
  }

  getPriority() {
    return this.priority
  }

  /**
   * Formats the result for display in the search modal.
   * Override in subclasses to provide custom formatting.
   * @param {Object} result - The search result object
   * @param {Object} context - Context (e.g., searchTerm for highlighting)
   * @returns {Object} Object with title, subtitle, and descriptionSegments
   */
  formatResultDisplay(result, context = null) {
    return {
      title: result.title,
      subtitle: result.subtitle,
      descriptionSegments: [],
    }
  }

  /**
   * Returns true if the result can be navigated to (has a valid URL).
   * Override in subclasses to provide custom logic.
   * @param {Object} result - The search result object
   * @param {Object} context - Context containing store reference
   * @returns {boolean}
   */
  isNavigable(result, context = null) {
    return true
  }

  /**
   * Gets the application ID from a result.
   * Override in subclasses for custom ID extraction logic.
   * @param {Object} result - The search result object
   * @returns {number|null}
   */
  _getApplicationId(result) {
    const id = parseInt(result?.id)
    return isNaN(id) ? null : id
  }

  /**
   * Attempts to focus/select the application in the sidebar as a fallback action.
   * @param {Object} result - The search result object
   * @param {Object} context - Context containing store reference
   * @returns {boolean} True if the action was taken, false otherwise
   */
  focusInSidebar(result, context = null) {
    const appId = this._getApplicationId(result)
    if (!appId) {
      return false
    }
    const application = this.app.$store.getters['application/get'](appId)
    if (application) {
      this.app.$store.dispatch('application/select', application)

      const applicationType = this.app.$registry.get(
        'application',
        application.type
      )
      applicationType.select(application, this.app)
      return true
    }
    return false
  }

  /**
   * Returns the i18n key suffix for the label to display when item is not navigable.
   * Returns null if no label should be shown.
   * @param {Object} result - The search result object
   * @param {Object} context - Context containing store reference
   * @returns {string|null}
   */
  getEmptyLabel(result, context = null) {
    if (this.isNavigable(result, context)) {
      return null
    }
    return this.app.$i18n.t('workspaceSearch.empty')
  }
}

export class ApplicationSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
  }

  _getApplicationChildren(application) {
    throw new Error('_getApplicationChildren must be implemented')
  }

  _getApplicationPath(application, children) {
    throw new Error('_getApplicationPath must be implemented')
  }

  _getApplicationId(result) {
    throw new Error('_getApplicationId must be implemented')
  }

  _getApplicationWithChildren(result, context) {
    const applicationId = this._getApplicationId(result)
    if (!applicationId) {
      return null
    }
    const application =
      this.app.$store.getters['application/get'](applicationId)
    if (!application) {
      return null
    }
    const children = this._getApplicationChildren(application)
    if (children && children.length > 0) {
      return application
    }
    return null
  }

  buildUrl(result, context = null) {
    const application = this._getApplicationWithChildren(result, context)
    if (!application) {
      return null
    }

    const children = [...this._getApplicationChildren(application)].sort(
      (a, b) => a.order - b.order
    )

    return this._getApplicationPath(application, children)
  }

  isNavigable(result, context = null) {
    return this._getApplicationWithChildren(result, context) !== null
  }
}
