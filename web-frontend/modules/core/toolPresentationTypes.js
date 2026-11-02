import { Registerable } from '@baserow/modules/core/registry'
import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'

export const WORKSPACE_TOOL_GROUP = 'workspace'

const MAX_INPUT_PREVIEW_LENGTH = 32768
const STATUSES = new Set(Object.values(STEP_STATUS))
const FALLBACK_LABELS = {
  [STEP_STATUS.RUNNING]: 'Using a tool',
  [STEP_STATUS.DONE]: 'Tool completed',
  [STEP_STATUS.FAILED]: 'Tool failed',
  [STEP_STATUS.STOPPED]: 'Tool interrupted',
}

/**
 * Presentation shared by workspace tools and configured actions. The stable type
 * selects only presentation, never the tool to execute or its permissions.
 * Modules register their own types in Core's `toolPresentation` namespace.
 */
export class ToolPresentationType extends Registerable {
  get icon() {
    return 'iconoir-tools'
  }

  /** Only workspace reads opt into the collapsible workspace activity group. */
  get group() {
    return null
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

const record = (value) =>
  value && typeof value === 'object' && !Array.isArray(value) ? value : {}

function genericText(t, key, fallback) {
  try {
    const text = t(key)
    return typeof text === 'string' && text.trim() && text !== key
      ? text
      : fallback
  } catch {
    return fallback
  }
}

function toolInput(presenter, step, t) {
  try {
    const input = presenter.getInput(step, t)
    const values = record(input?.values)
    if (!Object.keys(values).length) return null
    // Validate independently of the title so a broken preview cannot hide it.
    const json = JSON.stringify(values)
    if (json.length > MAX_INPUT_PREVIEW_LENGTH) return null
    const parsed = record(JSON.parse(json))
    if (!Object.keys(parsed).length) return null
    return { values: parsed, truncated: input.truncated === true }
  } catch {
    return null
  }
}

/** Resolve a safe activity without letting an unknown or broken type break chat. */
export function toolActivity(step, registry, t) {
  const data = record(step)
  const status = STATUSES.has(data.status) ? data.status : STEP_STATUS.STOPPED
  const fallback = {
    id: data.id,
    title: genericText(
      t,
      `toolPresentation.${status}`,
      FALLBACK_LABELS[status]
    ),
    status,
    icon: 'iconoir-tools',
    group: null,
    input: null,
  }
  try {
    const type = data.presentation_type || data.tool
    if (!registry.exists('toolPresentation', type)) return fallback
    const presenter = registry.get('toolPresentation', type)
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
      icon: presenter.icon,
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
        icon: 'iconoir-db',
        lines: [],
      }
      groups.push(group)
    }
    group.lines.push(activity)
    // Keep pending parallel calls visible; once settled, summarize the last
    // call in display order. Earlier outcomes remain on their individual lines.
    group.status = group.lines.some(
      (line) => line.status === STEP_STATUS.RUNNING
    )
      ? STEP_STATUS.RUNNING
      : activity.status
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
