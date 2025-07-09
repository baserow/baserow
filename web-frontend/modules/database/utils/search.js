export const SearchMode = {
  // Use this mode to search rows using LIKE operators against each
  // field type, and return an accurate `count` in the response.
  // This method is slow after a few thousand rows and dozens of fields.
  COMPAT: 'compat',
  // Use this mode to search rows using Postgres full-text search against
  // each field type, and provide a `count` in the response. This
  // method is much faster as tables grow in size.
  FT_WITH_COUNT: 'full-text-with-count',
}

export function getDefaultSearchModeFromEnv($config) {
  return $config.BASEROW_USE_PG_FULLTEXT_SEARCH === 'true'
    ? SearchMode.FT_WITH_COUNT
    : SearchMode.COMPAT
}
