// Must be the same as `src/baserow/contrib/database/views/models.py`.
export const DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY = 'default'

// Must be the same as `src/baserow/contrib/database/views/models.py`.
export const DEFAULT_SORT_TYPE_KEY = 'default'

export const GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING = {
  small: 33,
  medium: 55,
  large: 99,
}

export const GRID_VIEW_MIN_FIELD_WIDTH = 78

export const GRID_VIEW_MULTI_SELECT_AREA = 'area'
export const GRID_VIEW_MULTI_SELECT_CHECKBOX = 'checkbox'

export const LINKED_ITEMS_DEFAULT_LOAD_COUNT = 20
export const LINKED_ITEMS_LOAD_ALL = -1

// Soft UI cap on the number of group-bys a view can add. Views created with more
// (e.g. via the API) keep working; the UI just stops offering to add new ones.
export const MAX_GROUP_BYS = 5

export const UNIQUE_WITH_EMPTY_CONSTRAINT_NAME = 'unique_with_empty'

export const FIELD_CONSTRAINT_ERROR_CODES = [
  'ERROR_FIELD_CONSTRAINT',
  'ERROR_INVALID_FIELD_CONSTRAINT',
  'ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE',
]
