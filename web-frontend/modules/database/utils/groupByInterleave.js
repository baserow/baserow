import { fieldValuesAreEqualInObjects } from '@baserow/modules/database/utils/groupBy'

const HEADER_HEIGHT = 48
const ROW_HEIGHT = 33

export const COLLAPSED_GROUPS_MODE_EXPAND = 'expand'
export const COLLAPSED_GROUPS_MODE_COLLAPSE = 'collapse'

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
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
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
    y += getGroupVirtualHeight({
      groupValues: getGroupValues(entry, fieldsAtDepth),
      count: entry.count,
      depth: 0,
      groupByMetadata,
      collapsedGroups,
      collapsedGroupsMode,
      fields,
      registry,
    })
  }
  return null
}

export const GROUP_HEADER_HEIGHT = HEADER_HEIGHT
export const GROUP_ROW_HEIGHT = ROW_HEIGHT

function getGroupVirtualHeight({
  groupValues,
  count,
  depth,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  const fieldsAtDepth = fields.slice(0, depth + 1)
  let height = HEADER_HEIGHT

  if (
    isCollapsed(
      collapsedGroups,
      groupValues,
      fieldsAtDepth,
      registry,
      collapsedGroupsMode
    )
  ) {
    return height
  }

  if (depth === fields.length - 1) {
    return height + count * ROW_HEIGHT
  }

  const childDepth = depth + 1
  const childField = fields[childDepth]
  const childEntries = groupByMetadata[`field_${childField.id}`] || []
  const children = childEntries.filter((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
  )

  if (children.length === 0) {
    return height + count * ROW_HEIGHT
  }

  return (
    height +
    children.reduce((total, childEntry) => {
      const childFields = fields.slice(0, childDepth + 1)
      return (
        total +
        getGroupVirtualHeight({
          groupValues: getGroupValues(childEntry, childFields),
          count: childEntry.count,
          depth: childDepth,
          groupByMetadata,
          collapsedGroups,
          collapsedGroupsMode,
          fields,
          registry,
        })
      )
    }, 0)
  )
}

export function buildInterleavedList({
  rows,
  activeGroupBys,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  registry,
  fields = [],
  bufferStartIndex = 0,
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
    const rowIndex = bufferStartIndex + index
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
          registry,
          false,
          collapsedGroupsMode
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
        registry,
        collapsedGroupsMode
      )

      const isRealGroupBoundary =
        previousRow !== undefined ||
        isGroupAtVisibleRowIndex({
          groupValues: serializedGroupValues,
          depth,
          rowIndex,
          groupByMetadata,
          collapsedGroups,
          collapsedGroupsMode,
          fields: groupByFields,
          registry,
        })

      if (isNewGroup && isRealGroupBoundary) {
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
    collapsedGroupsMode,
    groupByFields,
    registry,
    bufferStartIndex,
    rows.length
  )

  insertCollapsedGroupHeaders(
    items,
    groupByMetadata,
    collapsedGroups,
    collapsedGroupsMode,
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

function isGroupAtVisibleRowIndex({
  groupValues,
  depth,
  rowIndex,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  const groupStartRowIndex = findGroupStartRowIndex({
    groupValues,
    depth,
    groupByMetadata,
    collapsedGroups,
    collapsedGroupsMode,
    fields,
    registry,
  })
  return groupStartRowIndex === rowIndex
}

function findGroupStartRowIndex({
  groupValues,
  depth,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  let rowIndex = 0

  function visitGroups(currentDepth, parentValues = null) {
    const field = fields[currentDepth]
    const fieldsAtDepth = fields.slice(0, currentDepth + 1)
    const parentFields = fields.slice(0, currentDepth)
    const entries = groupByMetadata[`field_${field.id}`] || []

    for (const entry of entries) {
      if (
        parentValues !== null &&
        !fieldValuesAreEqualInObjects(
          parentFields,
          registry,
          entry,
          parentValues,
          true,
          true
        )
      ) {
        continue
      }

      const entryGroupValues = getGroupValues(entry, fieldsAtDepth)
      const matchesTarget = fieldValuesAreEqualInObjects(
        fieldsAtDepth,
        registry,
        entryGroupValues,
        groupValues,
        true,
        true
      )

      if (currentDepth === depth && matchesTarget) {
        return rowIndex
      }

      if (
        currentDepth < depth &&
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          entryGroupValues,
          groupValues,
          true,
          true
        )
      ) {
        return visitGroups(currentDepth + 1, entryGroupValues)
      }

      rowIndex += getGroupVisibleRowCount({
        groupValues: entryGroupValues,
        count: entry.count,
        depth: currentDepth,
        groupByMetadata,
        collapsedGroups,
        collapsedGroupsMode,
        fields,
        registry,
      })
    }

    return null
  }

  return visitGroups(0)
}

function getGroupVisibleRowCount({
  groupValues,
  count,
  depth,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  const fieldsAtDepth = fields.slice(0, depth + 1)
  const collapsed = isCollapsed(
    collapsedGroups,
    groupValues,
    fieldsAtDepth,
    registry,
    collapsedGroupsMode,
    true
  )

  if (collapsed) {
    return 0
  }

  if (depth === fields.length - 1) {
    return count
  }

  const childDepth = depth + 1
  const childField = fields[childDepth]
  const childEntries = groupByMetadata[`field_${childField.id}`] || []
  const children = childEntries.filter((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
  )

  if (children.length === 0) {
    return count
  }

  return children.reduce((total, childEntry) => {
    const childFields = fields.slice(0, childDepth + 1)
    return (
      total +
      getGroupVisibleRowCount({
        groupValues: getGroupValues(childEntry, childFields),
        count: childEntry.count,
        depth: childDepth,
        groupByMetadata,
        collapsedGroups,
        collapsedGroupsMode,
        fields,
        registry,
      })
    )
  }, 0)
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

function isCollapsed(
  collapsedGroups,
  groupValues,
  fieldsAtDepth,
  registry,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  groupValuesIsGroup = false
) {
  const inList = collapsedGroups.some((entry) => {
    if (Object.keys(entry).length !== fieldsAtDepth.length) {
      return false
    }
    // collapsedGroup holds metadata-form values (e.g. an option ID); groupValues
    // holds row-form values (e.g. {id, value, color}). Pass object1IsGroup so
    // the metadata side is converted via getRowValueFromGroupValue first.
    return fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      groupValuesIsGroup
    )
  })

  return collapsedGroupsMode === COLLAPSED_GROUPS_MODE_COLLAPSE
    ? !inList
    : inList
}

function isAncestorCollapsed(
  collapsedGroups,
  groupValues,
  groupByFields,
  depth,
  registry,
  groupValuesIsGroup = false,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND
) {
  for (let ancestorDepth = 0; ancestorDepth < depth; ancestorDepth++) {
    const fieldsAtDepth = groupByFields.slice(0, ancestorDepth + 1)
    const ancestorValues = fieldsAtDepth.reduce((acc, f) => {
      acc[`field_${f.id}`] = groupValues[`field_${f.id}`]
      return acc
    }, {})
    if (
      isCollapsed(
        collapsedGroups,
        ancestorValues,
        fieldsAtDepth,
        registry,
        collapsedGroupsMode,
        groupValuesIsGroup
      )
    ) {
      return true
    }
  }
  return false
}

function insertMissingDepth0Headers(
  items,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
  bufferStartIndex,
  bufferLength
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
    const collapsed = isCollapsed(
      collapsedGroups,
      groupValues,
      fieldsAtDepth,
      registry,
      collapsedGroupsMode,
      true
    )

    // In expand-mode, only synthesize headers for collapsed groups — uncollapsed
    // ones get their headers from the row-iteration above, anchored to the real
    // row positions in the buffer. Synthesizing them here would put them at
    // the wrong virtual y when the buffer sits mid-group.
    //
    // In collapse-mode every group is conceptually a header-tall placeholder by
    // default, including the just-toggled exception whose rows haven't arrived
    // yet. Synthesize for all entries; `alreadyRendered` deduplicates against
    // headers the row-iteration already added once the response lands.
    if (collapsedGroupsMode === COLLAPSED_GROUPS_MODE_EXPAND && !collapsed) {
      return
    }

    if (collapsedGroupsMode === COLLAPSED_GROUPS_MODE_EXPAND && collapsed) {
      const groupStartRowIndex = findGroupStartRowIndex({
        groupValues,
        depth: 0,
        groupByMetadata,
        collapsedGroups,
        collapsedGroupsMode,
        fields,
        registry,
      })
      if (
        groupStartRowIndex === null ||
        groupStartRowIndex < bufferStartIndex ||
        groupStartRowIndex > bufferStartIndex + bufferLength
      ) {
        return
      }
    }

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
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry
) {
  for (let depth = 1; depth < fields.length; depth++) {
    const field = fields[depth]
    const fieldsAtDepth = fields.slice(0, depth + 1)
    const metadataEntries = groupByMetadata[`field_${field.id}`] || []

    metadataEntries.forEach((entry) => {
      const groupValues = getGroupValues(entry, fieldsAtDepth)
      const collapsed = isCollapsed(
        collapsedGroups,
        groupValues,
        fieldsAtDepth,
        registry,
        collapsedGroupsMode,
        true
      )

      // Same rule as `insertMissingDepth0Headers`: in expand-mode skip
      // uncollapsed groups (their headers come from row-iteration), in
      // collapse-mode synthesize everything so a just-toggled exception
      // doesn't blink out of existence while the refresh is in flight.
      if (collapsedGroupsMode === COLLAPSED_GROUPS_MODE_EXPAND && !collapsed) {
        return
      }

      if (
        isAncestorCollapsed(
          collapsedGroups,
          groupValues,
          fields,
          depth,
          registry,
          true,
          collapsedGroupsMode
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
            groupValues,
            true,
            true
          )
      )

      if (alreadyRendered) {
        return
      }

      // Only insert a deeper-level collapsed header if its parent group is
      // present in the items list — otherwise we'd plant a Design+High header
      // somewhere inside Development's section because there's no Design
      // anchor to position it against.
      const parentFields = fields.slice(0, depth)
      const parentValues = parentFields.reduce((acc, parentField) => {
        acc[`field_${parentField.id}`] = groupValues[`field_${parentField.id}`]
        return acc
      }, {})
      const parentItemIndex = items.findIndex(
        (item) =>
          item.type === 'header' &&
          item.depth === depth - 1 &&
          fieldValuesAreEqualInObjects(
            parentFields,
            registry,
            item.groupValues,
            parentValues,
            true,
            true
          )
      )
      if (parentItemIndex === -1) {
        return
      }

      const header = {
        type: 'header',
        depth,
        field,
        groupValues,
        count: entry.count,
        collapsed,
      }

      // Find the next sibling at this depth WITHIN the same parent. We bound
      // the search to the parent's section so we only consider items that
      // belong to it.
      const collapsedMetadataIndex = findMetadataIndex(
        metadataEntries,
        groupValues,
        fieldsAtDepth,
        registry
      )

      let parentSectionEnd = items.length
      for (let i = parentItemIndex + 1; i < items.length; i++) {
        const item = items[i]
        if (item.type === 'header' && item.depth <= depth - 1) {
          parentSectionEnd = i
          break
        }
      }

      let insertIndex = -1
      for (let i = parentItemIndex + 1; i < parentSectionEnd; i++) {
        const item = items[i]
        if (item.type !== 'header' || item.depth !== depth) continue
        const itemMetadataIndex = findMetadataIndex(
          metadataEntries,
          item.groupValues,
          fieldsAtDepth,
          registry
        )
        if (collapsedMetadataIndex < itemMetadataIndex) {
          insertIndex = i
          break
        }
      }

      items.splice(
        insertIndex === -1 ? parentSectionEnd : insertIndex,
        0,
        header
      )
    })
  }
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
