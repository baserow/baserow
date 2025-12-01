export class BaseSearchType {
  constructor() {
    this.type = null
    this.name = null
    this.icon = 'iconoir-search'
    this.priority = 10
  }

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

  // Default formatting returns plain title/subtitle and no description segments
  formatResultDisplay(result, context = null) {
    return {
      title: result.title,
      subtitle: result.subtitle,
      descriptionSegments: [],
    }
  }

  // Returns true if the result can be navigated to (has a valid URL)
  // Override in subclasses to provide custom logic
  isNavigable(result, context = null) {
    return true
  }

  // Attempts to focus/select the result in the sidebar as a fallback action
  // Returns true if the action was taken, false otherwise
  // Override in subclasses to provide custom logic
  focusInSidebar(result, context = null) {
    return false
  }
}
