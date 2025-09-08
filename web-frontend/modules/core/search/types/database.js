import { BaseSearchType } from './base'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

export class DatabaseSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database'
    this.name = 'Database'
    this.icon = new DatabaseApplicationType().getIconClass()
    this.priority = 1
  }

  buildUrl(result, context = null) {
    if (!result.metadata || !result.metadata.database_id) {
      return null
    }

    if (context && context.store) {
      const application = context.store.getters['application/get'](
        result.metadata.database_id
      )
      if (application && application.tables && application.tables.length > 0) {
        const tables = application.tables
          .map((t) => t)
          .sort((a, b) => a.order - b.order)

        if (tables.length > 0) {
          return `/database/${result.metadata.database_id}/table/${tables[0].id}`
        }
      }
    }

    return null
  }
}

export class DatabaseTableSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database_table'
    this.name = 'Tables'
    this.icon = 'iconoir-table'
    this.priority = 2
  }

  buildUrl(result, context = null) {
    if (
      !result.metadata ||
      !result.metadata.database_id ||
      !result.metadata.table_id
    ) {
      return null
    }

    return `/database/${result.metadata.database_id}/table/${result.metadata.table_id}`
  }
}

export class DatabaseFieldSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database_field'
    this.name = 'Fields'
    this.icon = 'iconoir-database-check'
    this.priority = 6
  }

  buildUrl(result, context = null) {
    if (
      !result.metadata ||
      !result.metadata.database_id ||
      !result.metadata.table_id
    ) {
      return null
    }

    return `/database/${result.metadata.database_id}/table/${result.metadata.table_id}`
  }
}

export class DatabaseRowSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'database_row'
    this.name = 'Rows'
    this.icon = 'iconoir-page'
    this.priority = 7
  }

  buildUrl(result, context = null) {
    if (
      !result.metadata ||
      !result.metadata.database_id ||
      !result.metadata.table_id ||
      !result.metadata.row_id
    ) {
      return null
    }

    return `/database/${result.metadata.database_id}/table/${result.metadata.table_id}/row/${result.metadata.row_id}`
  }

  // Convert description with [[H]]...[[/H]] markers into segments for safe rendering
  formatResultDisplay(result) {
    const base = {
      title: result.title,
      subtitle: result.subtitle,
      descriptionSegments: [],
    }
    const desc = result.description || ''
    if (!desc) return base

    const start = '[[H]]'
    const stop = '[[/H]]'
    const segments = []
    let i = 0
    while (i < desc.length) {
      const startIdx = desc.indexOf(start, i)
      if (startIdx === -1) {
        segments.push({ text: desc.slice(i), highlighted: false })
        break
      }
      if (startIdx > i) {
        segments.push({ text: desc.slice(i, startIdx), highlighted: false })
      }
      const stopIdx = desc.indexOf(stop, startIdx + start.length)
      if (stopIdx === -1) {
        // No closing marker, treat rest as normal text
        segments.push({ text: desc.slice(startIdx), highlighted: false })
        break
      }
      const inner = desc.slice(startIdx + start.length, stopIdx)
      segments.push({ text: inner, highlighted: true })
      i = stopIdx + stop.length
    }
    // Normalize spaces around hyphens across segment boundaries to avoid extra spaces
    for (let j = 0; j < segments.length - 1; j++) {
      const cur = segments[j]
      const nxt = segments[j + 1]
      if (cur.text.endsWith(' ') && nxt.text.startsWith('-')) {
        cur.text = cur.text.slice(0, -1)
      }
      if (cur.text.endsWith('-') && nxt.text.startsWith(' ')) {
        nxt.text = nxt.text.slice(1)
      }
      // Handle cases where spaces were inserted on both sides of a hyphen
      if (cur.text.endsWith(' ') && nxt.text.startsWith(' -')) {
        cur.text = cur.text.slice(0, -1)
        nxt.text = nxt.text.slice(1)
      }
    }
    base.descriptionSegments = segments
    return base
  }
}
