import { BaseSearchType } from './base'

export class SearchTypeRegistry {
  constructor() {
    this.types = new Map()
  }

  register(searchType) {
    if (!(searchType instanceof BaseSearchType)) {
      throw new TypeError('Search type must extend BaseSearchType')
    }

    if (!searchType.type) {
      throw new Error('Search type must define a type')
    }

    this.types.set(searchType.type, searchType)
  }

  get(type) {
    return this.types.get(type)
  }

  getAll() {
    return Array.from(this.types.values()).sort(
      (a, b) => a.priority - b.priority
    )
  }

  has(type) {
    return this.types.has(type)
  }

  buildUrl(type, result, context = null) {
    const searchType = this.get(type)
    if (!searchType) {
      console.warn(`No search type found for: ${type}`)
      return null
    }
    return searchType.buildUrl(result, context)
  }

  getIcon(type) {
    const searchType = this.get(type)
    if (!searchType) {
      return 'iconoir-search'
    }
    return searchType.getIcon()
  }

  formatResultDisplay(type, result, context = null) {
    const searchType = this.get(type)
    return searchType.formatResultDisplay(result, context)
  }
}

export const searchTypeRegistry = new SearchTypeRegistry()
