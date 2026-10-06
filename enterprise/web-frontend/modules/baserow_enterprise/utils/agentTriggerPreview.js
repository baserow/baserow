/**
 * Turns the event payload that started a triggered conversation into the
 * rows the trigger block previews, per trigger type. Unknown shapes fall
 * back to the top-level keys so the raw JSON is never the only option.
 */

const ROW_TRIGGERS = [
  'rows_created',
  'rows_updated',
  'rows_deleted',
  'fields_updated',
]
const MAX_ROWS = 20
const MAX_COLUMNS = 8

export function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function formatValue(value) {
  if (value === null || value === undefined || value === '') {
    return ''
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

export function rowsTable(rows) {
  const list = (Array.isArray(rows) ? rows : [])
    .filter(isObject)
    .slice(0, MAX_ROWS)
  if (list.length === 0) {
    return null
  }
  const columns = []
  for (const row of list) {
    for (const key of Object.keys(row)) {
      if (key !== 'order' && !columns.includes(key)) {
        columns.push(key)
      }
    }
  }
  return {
    columns: columns.slice(0, MAX_COLUMNS),
    rows: list.map((row) =>
      columns.slice(0, MAX_COLUMNS).map((column) => formatValue(row[column]))
    ),
  }
}

function genericFields(payload) {
  if (!isObject(payload)) {
    return []
  }
  return Object.entries(payload).map(([key, value]) => ({
    key,
    value: formatValue(value),
  }))
}

/**
 * @param {string} triggerType The agent trigger type (chat.trigger_type).
 * @param {*} payload The event payload.
 * @param {object} helpers `t(key, values)`, `formatDate(iso)`,
 *   `tableLabel(tableId)` and `rowLabel(tableId, rowId)`.
 * @returns {{quote?: object, fields: object[], table?: object}|null}
 */
export function buildTriggerPreview(triggerType, payload, helpers) {
  if (payload === null || payload === undefined) {
    return null
  }
  const { t, formatDate, tableLabel, rowLabel } = helpers
  const type = String(triggerType || '').replace(/^local_baserow_/, '')

  if (type === 'row_comment_created' && isObject(payload)) {
    const mentions = (payload.mentions || [])
      .map((mention) => mention?.name)
      .filter(Boolean)
    const fields = [
      {
        key: t('agentChatTrigger.row'),
        value: rowLabel(payload.table_id, payload.row_id),
        kind: 'row',
      },
      {
        key: t('agentChatTrigger.table'),
        value: tableLabel(payload.table_id),
        kind: 'table',
      },
      {
        key: t('agentChatTrigger.posted'),
        value: formatDate(payload.created_on),
      },
    ]
    if (mentions.length > 0) {
      fields.push({
        key: t('agentChatTrigger.mentioned'),
        value: mentions.join(', '),
        kind: 'member',
      })
    }
    return {
      quote: {
        author: payload.user?.name || '',
        text: payload.message || '',
        at: formatDate(payload.created_on),
      },
      fields: fields.filter((field) => field.value),
    }
  }

  if (ROW_TRIGGERS.includes(type) && isObject(payload)) {
    const table = rowsTable(payload.results)
    return table ? { fields: [], table } : { fields: genericFields(payload) }
  }

  if (type === 'periodic' && isObject(payload)) {
    return {
      fields: [
        {
          key: t('agentChatTrigger.started'),
          value: formatDate(payload.triggered_at),
        },
        {
          key: t('agentChatTrigger.nextRun'),
          value: formatDate(payload.next_run_at),
        },
      ].filter((field) => field.value),
    }
  }

  if (type === 'http_trigger' && isObject(payload)) {
    return {
      fields: [
        {
          key: t('agentChatTrigger.method'),
          value: formatValue(payload.method),
        },
        {
          key: t('agentChatTrigger.query'),
          value: formatValue(payload.query_params),
        },
        {
          key: t('agentChatTrigger.headers'),
          value: formatValue(payload.headers),
        },
        { key: t('agentChatTrigger.body'), value: formatValue(payload.body) },
      ].filter((field) => field.value),
    }
  }

  if (type === 'email_trigger' && isObject(payload)) {
    const address = (item) =>
      isObject(item)
        ? item.name
          ? `${item.name} <${item.address}>`
          : item.address || ''
        : formatValue(item)
    const list = (items) =>
      Array.isArray(items) ? items.map(address).filter(Boolean).join(', ') : ''
    return {
      fields: [
        { key: t('agentChatTrigger.from'), value: address(payload.from) },
        { key: t('agentChatTrigger.to'), value: list(payload.to) },
        { key: t('agentChatTrigger.cc'), value: list(payload.cc) },
        {
          key: t('agentChatTrigger.subject'),
          value: formatValue(payload.subject),
        },
      ].filter((field) => field.value),
      body: payload.body_text || '',
    }
  }

  const fields = genericFields(payload)
  return fields.length > 0 ? { fields } : null
}
