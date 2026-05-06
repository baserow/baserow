import { fieldValuesAreEqualInObjects } from '@baserow/modules/database/utils/groupBy'

const HEADER_HEIGHT = 48
const ROW_HEIGHT = 33

/**
 * Returns the virtual y-coordinate where the depth-0 group identified by
 * `groupValues` starts (i.e. the top of its header), and the count of rows in
 * that group. Returns null if the group isn't present in the metadata — that
 * happens when the buffer hasn't covered it yet, in which case the caller
 * should leave the scroll position alone.
 */
export function findDepth0GroupPosition({
  groupValues,
  groupByMetadata,
  collapsedGroups,
  fields,
  registry,
}) {
  if (fields.length === 0) return null
  const fieldsAtDepth = fields.slice(0, 1)
  const fieldKey = `field_${fields[0].id}`
  const entries = groupByMetadata[fieldKey] || []
  let y = 0
  for (const entry of entries) {
    const matches = fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
    if (matches) {
      return { y, count: entry.count }
    }
    const isCollapsed = collapsedGroups.some(
      (cg) =>
        Object.keys(cg).length === 1 &&
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          cg,
          entry,
          true,
          true
        )
    )
    y += HEADER_HEIGHT
    if (!isCollapsed) {
      y += entry.count * ROW_HEIGHT
    }
  }
  return null
}

export const GROUP_HEADER_HEIGHT = HEADER_HEIGHT
export const GROUP_ROW_HEIGHT = ROW_HEIGHT

export function buildInterleavedList({
  rows,
  activeGroupBys,
  groupByMetadata,
  collapsedGroups,
  registry,
  fields = [],
}) {
  if (activeGroupBys.length === 0) {
    return rows.map((row) => ({ type: 'row', row }))
  }

  const groupByFields = activeGroupBys
    .map(
      (groupBy, index) =>
        fields.find((field) => field.id === groupBy.field) || fields[index]
    )
    .filter(Boolean)

  if (groupByFields.length === 0) {
    return rows.map((row) => ({ type: 'row', row }))
  }

  const items = []

  rows.forEach((row, index) => {
    const previousRow = rows[index - 1]
    let skipRow = false

    for (let depth = 0; depth < groupByFields.length; depth++) {
      const fieldsAtDepth = groupByFields.slice(0, depth + 1)
      const groupValues = getGroupValues(row, fieldsAtDepth)

      if (
        isAncestorCollapsed(
          collapsedGroups,
          groupValues,
          groupByFields,
          depth,
          registry
        )
      ) {
        skipRow = true
        break
      }

      const isNewGroup =
        previousRow === undefined ||
        !fieldValuesAreEqualInObjects(fieldsAtDepth, registry, previousRow, row)

      const metadataEntry = lookupMetadataEntry(
        groupByMetadata,
        groupByFields,
        depth,
        groupValues,
        registry
      )
      const serializedGroupValues = metadataEntry
        ? getGroupValues(metadataEntry, fieldsAtDepth)
        : groupValues
      const collapsed = isCollapsed(
        collapsedGroups,
        groupValues,
        fieldsAtDepth,
        registry
      )

      if (isNewGroup) {
        items.push({
          type: 'header',
          depth,
          field: groupByFields[depth],
          groupValues: serializedGroupValues,
          count: metadataEntry?.count ?? -1,
          collapsed,
        })
      }

      if (collapsed) {
        skipRow = true
        break
      }
    }

    if (!skipRow) {
      items.push({ type: 'row', row })
    }
  })

  // Backfill missing depth-0 headers from metadata. This covers both
  // collapsed groups (whose rows the backend excluded) and the brief window
  // after a user re-expands a group, before the new rows arrive — without it
  // the header would vanish until the next refresh completes.
  insertMissingDepth0Headers(
    items,
    groupByMetadata,
    collapsedGroups,
    groupByFields,
    registry
  )

  insertCollapsedGroupHeaders(
    items,
    groupByMetadata,
    collapsedGroups,
    groupByFields,
    registry
  )

  return items
}

function getGroupValues(row, fields) {
  return fields.reduce((values, field) => {
    values[`field_${field.id}`] = row[`field_${field.id}`]
    return values
  }, {})
}

function lookupCount(
  metadata,
  fields,
  depth,
  groupValues,
  registry,
  groupValuesIsGroup = false
) {
  return (
    lookupMetadataEntry(
      metadata,
      fields,
      depth,
      groupValues,
      registry,
      groupValuesIsGroup
    )?.count ?? -1
  )
}

function lookupMetadataEntry(
  metadata,
  fields,
  depth,
  groupValues,
  registry,
  groupValuesIsGroup = false
) {
  const field = fields[depth]
  const fieldKey = `field_${field.id}`
  const entries = metadata[fieldKey] || []
  const fieldsAtDepth = fields.slice(0, depth + 1)
  return entries.find((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      groupValuesIsGroup
    )
  )
}

function isCollapsed(collapsedGroups, groupValues, fieldsAtDepth, registry) {
  return collapsedGroups.some((collapsedGroup) => {
    if (Object.keys(collapsedGroup).length !== fieldsAtDepth.length) {
      return false
    }
    // collapsedGroup holds metadata-form values (e.g. an option ID); groupValues
    // holds row-form values (e.g. {id, value, color}). Pass object1IsGroup so
    // the metadata side is converted via getRowValueFromGroupValue first.
    return fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      collapsedGroup,
      groupValues,
      true
    )
  })
}

function isAncestorCollapsed(
  collapsedGroups,
  groupValues,
  groupByFields,
  depth,
  registry,
  groupValuesIsGroup = false
) {
  return collapsedGroups.some((collapsedGroup) => {
    const collapsedDepth = getEntryDepth(collapsedGroup, groupByFields)
    if (collapsedDepth < 0 || collapsedDepth >= depth) {
      return false
    }
    return fieldValuesAreEqualInObjects(
      groupByFields.slice(0, collapsedDepth + 1),
      registry,
      collapsedGroup,
      groupValues,
      true,
      groupValuesIsGroup
    )
  })
}

function insertMissingDepth0Headers(
  items,
  groupByMetadata,
  collapsedGroups,
  fields,
  registry
) {
  if (fields.length === 0) {
    return
  }
  const field = fields[0]
  const fieldsAtDepth = [field]
  const fieldKey = `field_${field.id}`
  const metadataEntries = groupByMetadata[fieldKey] || []

  metadataEntries.forEach((entry, metadataIndex) => {
    const groupValues = getGroupValues(entry, fieldsAtDepth)

    const alreadyRendered = items.some(
      (item) =>
        item.type === 'header' &&
        item.depth === 0 &&
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          item.groupValues,
          groupValues,
          true,
          true
        )
    )
    if (alreadyRendered) {
      return
    }

    const collapsed = collapsedGroups.some(
      (collapsedGroup) =>
        Object.keys(collapsedGroup).length === 1 &&
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          collapsedGroup,
          groupValues,
          true,
          true
        )
    )

    const insertIndex = items.findIndex((item) => {
      if (item.type !== 'header' || item.depth !== 0) {
        return false
      }
      const itemMetadataIndex = metadataEntries.findIndex((e) =>
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          e,
          item.groupValues,
          true,
          true
        )
      )
      const resolvedIndex =
        itemMetadataIndex === -1 ? Number.MAX_SAFE_INTEGER : itemMetadataIndex
      return metadataIndex < resolvedIndex
    })

    items.splice(insertIndex === -1 ? items.length : insertIndex, 0, {
      type: 'header',
      depth: 0,
      field,
      groupValues,
      count: entry.count,
      collapsed,
    })
  })
}

function insertCollapsedGroupHeaders(
  items,
  groupByMetadata,
  collapsedGroups,
  fields,
  registry
) {
  collapsedGroups.forEach((collapsedGroup) => {
    const depth = getEntryDepth(collapsedGroup, fields)
    if (depth <= 0) {
      // Depth-0 collapsed headers are inserted by `insertMissingDepth0Headers`.
      return
    }

    const fieldsAtDepth = fields.slice(0, depth + 1)
    if (
      isAncestorCollapsed(
        collapsedGroups,
        collapsedGroup,
        fields,
        depth,
        registry,
        true
      )
    ) {
      return
    }

    const alreadyRendered = items.some(
      (item) =>
        item.type === 'header' &&
        item.depth === depth &&
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          item.groupValues,
          collapsedGroup,
          true,
          true
        )
    )

    if (alreadyRendered) {
      return
    }

    const field = fields[depth]
    const header = {
      type: 'header',
      depth,
      field,
      groupValues: { ...collapsedGroup },
      count: lookupCount(
        groupByMetadata,
        fields,
        depth,
        collapsedGroup,
        registry,
        true
      ),
      collapsed: true,
    }

    const metadataEntries = groupByMetadata[`field_${field.id}`] || []
    const collapsedMetadataIndex = findMetadataIndex(
      metadataEntries,
      collapsedGroup,
      fieldsAtDepth,
      registry
    )
    const insertIndex = items.findIndex((item) => {
      if (item.type !== 'header' || item.depth !== depth) {
        return false
      }
      const itemMetadataIndex = findMetadataIndex(
        metadataEntries,
        item.groupValues,
        fieldsAtDepth,
        registry
      )
      return collapsedMetadataIndex < itemMetadataIndex
    })

    items.splice(insertIndex === -1 ? items.length : insertIndex, 0, header)
  })
}

function findMetadataIndex(entries, groupValues, fieldsAtDepth, registry) {
  const index = entries.findIndex((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
  )
  return index === -1 ? Number.MAX_SAFE_INTEGER : index
}

function getEntryDepth(entry, fields) {
  for (let depth = fields.length - 1; depth >= 0; depth--) {
    if (
      Object.prototype.hasOwnProperty.call(entry, `field_${fields[depth].id}`)
    ) {
      return depth
    }
  }
  return -1
}
