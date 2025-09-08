import { searchTypeRegistry } from './registry'

import {
  DatabaseSearchType,
  DatabaseTableSearchType,
  DatabaseFieldSearchType,
  DatabaseRowSearchType,
} from './database'
import { BuilderSearchType } from './builder'
import { DashboardSearchType } from './dashboard'
import { AutomationSearchType } from './automation'

export function registerSearchTypes() {
  searchTypeRegistry.register(new DatabaseSearchType())
  searchTypeRegistry.register(new DatabaseTableSearchType())
  searchTypeRegistry.register(new DatabaseFieldSearchType())
  searchTypeRegistry.register(new DatabaseRowSearchType())
  searchTypeRegistry.register(new BuilderSearchType())
  searchTypeRegistry.register(new DashboardSearchType())
  searchTypeRegistry.register(new AutomationSearchType())
}

export { searchTypeRegistry }
export { BaseSearchType } from './base'
export { SearchTypeRegistry } from './registry'
