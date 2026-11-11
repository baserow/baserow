import { Registerable } from '@baserow/modules/core/registry'
import {
  STEP_ERROR_CODE,
  STEP_STATUS,
} from '@baserow/modules/core/chatRuns/constants'

export const WORKSPACE_TOOL_GROUP = 'workspace'

const STATUSES = new Set(Object.values(STEP_STATUS))
const FALLBACK_LABELS = {
  [STEP_STATUS.RUNNING]: 'Using a tool',
  [STEP_STATUS.WAITING]: 'Tool waiting for approval',
  [STEP_STATUS.DONE]: 'Tool completed',
  [STEP_STATUS.FAILED]: 'Tool failed',
  [STEP_STATUS.REJECTED]: 'Tool rejected',
  [STEP_STATUS.STOPPED]: 'Tool interrupted',
}
const STATUS_LABELS = {
  [STEP_STATUS.RUNNING]: 'toolPresentation.statusRunning',
  [STEP_STATUS.WAITING]: 'toolPresentation.statusWaiting',
  [STEP_STATUS.DONE]: 'toolPresentation.statusDone',
  [STEP_STATUS.FAILED]: 'toolPresentation.statusFailed',
  [STEP_STATUS.REJECTED]: 'toolPresentation.statusRejected',
  [STEP_STATUS.STOPPED]: 'toolPresentation.statusInterrupted',
}
const FAILURE_LABELS = new Map([
  [STEP_ERROR_CODE.NOT_FOUND, 'toolPresentation.failureNotFound'],
  [
    STEP_ERROR_CODE.PERMISSION_DENIED,
    'toolPresentation.failurePermissionDenied',
  ],
  [STEP_ERROR_CODE.INVALID_INPUT, 'toolPresentation.failureInvalidInput'],
  [STEP_ERROR_CODE.INVALID_FORMULA, 'toolPresentation.failureInvalidFormula'],
  [STEP_ERROR_CODE.CONFLICT, 'toolPresentation.failureConflict'],
  [STEP_ERROR_CODE.FAILED, 'toolPresentation.failureFailed'],
  [STEP_ERROR_CODE.NOT_RUN, 'toolPresentation.failureNotRun'],
])
const MAX_MESSAGE_LENGTH = 1000

/**
 * How a tool's calls look in chat, registered under the tool's name in Core's
 * `toolPresentation` namespace. It never selects what runs or what is allowed.
 */
export class ToolPresentationType extends Registerable {
  /** Only workspace reads opt into the collapsible workspace activity group. */
  get group() {
    return null
  }

  /**
   * Whether this type presents a tool registered under another name. Tools
   * named at runtime, like those of an MCP server, can't be registered one by
   * one, so their type claims them by name instead.
   */
  matchesTool(name) {
    return false
  }

  getLabel(t) {
    return t('toolPresentation.tool')
  }

  getDescription(t) {
    return ''
  }

  /** Receives explicitly approved display input and facts, never raw results. */
  getActivity(step, t) {
    return t(`toolPresentation.${step.status}`)
  }

  /** Opt in to the backend's curated input preview; hidden by default. */
  getInput(step, t) {
    return null
  }
}

/** The type registered under the tool's name, or one that claims the name. */
function findPresenter(registry, name) {
  if (registry.exists('toolPresentation', name)) {
    return registry.get('toolPresentation', name)
  }
  if (typeof name !== 'string') return null
  return (
    registry
      .getList('toolPresentation')
      .find((presenter) => presenter.matchesTool(name)) ?? null
  )
}

const record = (value) =>
  value && typeof value === 'object' && !Array.isArray(value) ? value : {}

function genericText(t, key, fallback, values) {
  try {
    const text = t(key, values)
    return typeof text === 'string' && text.trim() && text !== key
      ? text
      : fallback
  } catch {
    return fallback
  }
}

const text = (value) =>
  typeof value === 'string' ? value.trim().slice(0, MAX_MESSAGE_LENGTH) : ''

function failureHint(data, status, t) {
  if (status !== STEP_STATUS.FAILED) return ''
  const message = text(data.error_message)
  if (message) return message
  const key =
    FAILURE_LABELS.get(data.error_code) || 'toolPresentation.failureFailed'
  return genericText(t, key, 'This tool call failed.')
}

/** The items a partly successful call couldn't change, as people-facing text. */
function itemErrors(data) {
  return (Array.isArray(data.item_errors) ? data.item_errors : [])
    .filter((error) => record(error) === error && text(error.message))
    .map((error) => ({
      item: String(error.item ?? ''),
      message: text(error.message),
    }))
}

/** Name a step's status; an interrupted change may have completed. */
export function stepStatusLabel({ status, changesData, partial }, t) {
  if (status === STEP_STATUS.STOPPED && changesData) {
    return t('toolPresentation.statusStopped')
  }
  if (status === STEP_STATUS.DONE && partial) {
    return t('toolPresentation.statusPartial')
  }
  return t(STATUS_LABELS[status])
}

/** Describe a step's status in words, with why it failed. */
export function stepStatusText(step, t) {
  const label = stepStatusLabel(step, t)
  return step.status === STEP_STATUS.FAILED
    ? `${label} ${step.failureHint || t('toolPresentation.failureFailed')}`
    : label
}

function toolInput(presenter, step, t) {
  try {
    const input = presenter.getInput(step, t)
    const values = record(input?.values)
    return Object.keys(values).length
      ? { values, truncated: input.truncated === true }
      : null
  } catch {
    return null
  }
}

/** Resolve a safe activity without letting an unknown or broken type break chat. */
export function toolActivity(step, registry, t) {
  const data = record(step)
  const status = STATUSES.has(data.status) ? data.status : STEP_STATUS.STOPPED
  const failedItems = itemErrors(data)
  const fallback = {
    id: data.id,
    title: genericText(
      t,
      `toolPresentation.${status}`,
      FALLBACK_LABELS[status]
    ),
    status,
    changesData: data.changes_data === true,
    group: null,
    input: null,
    failureHint: failureHint(data, status, t),
    itemErrors: failedItems,
    partial: status === STEP_STATUS.DONE && failedItems.length > 0,
  }
  try {
    const presenter = findPresenter(registry, data.tool)
    if (!presenter) return fallback
    const translate = (key, values, count) => {
      const text = t(key, values, count)
      const exists = presenter.app?.$i18n?.te?.(key)
      if (
        typeof text !== 'string' ||
        !text.trim() ||
        (text === key && exists !== true)
      ) {
        throw new Error(`Missing tool presentation translation: ${key}`)
      }
      return text
    }
    const normalized = {
      ...data,
      status,
      input: record(data.input),
      facts: record(data.facts),
    }
    const title = presenter.getActivity(normalized, translate)
    if (typeof title !== 'string' || !title.trim()) return fallback
    return {
      ...fallback,
      title,
      group: !data.changes_data ? presenter.group : null,
      input: toolInput(presenter, normalized, translate),
    }
  } catch {
    return fallback
  }
}

/** Group adjacent workspace reads, preserving each write/action's own card. */
export function groupToolSteps(steps, registry, t) {
  const groups = []
  for (const step of Array.isArray(steps) ? steps : []) {
    if (step?.status === STEP_STATUS.SKIPPED) continue
    const activity = toolActivity(step, registry, t)
    if (activity.group !== WORKSPACE_TOOL_GROUP) {
      groups.push({ ...activity, lines: [] })
      continue
    }
    let group = groups.at(-1)
    if (!group?.lines.length) {
      group = {
        id: activity.id,
        title: '',
        status: activity.status,
        lines: [],
      }
      groups.push(group)
    }
    group.lines.push(activity)
    // Earlier outcomes stay visible on their own lines.
    group.status = group.lines.some(
      (line) => line.status === STEP_STATUS.RUNNING
    )
      ? STEP_STATUS.RUNNING
      : activity.status
    group.failureHint =
      group.status === STEP_STATUS.FAILED ? activity.failureHint : ''
    group.title = genericText(
      t,
      group.status === STEP_STATUS.RUNNING
        ? 'toolPresentation.workspaceRunning'
        : group.status === STEP_STATUS.DONE
          ? 'toolPresentation.workspaceDone'
          : 'toolPresentation.workspace',
      'Workspace activity'
    )
  }
  return groups
}
