import { Registerable } from '@baserow/modules/core/registry'

const STATUSES = new Set(['running', 'done', 'failed', 'stopped'])
const FALLBACK_LABELS = {
  running: 'Using a tool',
  done: 'Tool completed',
  failed: 'Tool failed',
  stopped: 'Tool interrupted',
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

  /** Receives safe display summaries and facts, never raw arguments/results. */
  getActivity(step, t) {
    return t(`toolPresentation.${step.status}`)
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

/** Resolve a safe activity without letting an unknown or broken type break chat. */
export function toolActivity(step, registry, t) {
  const data = record(step)
  const status = STATUSES.has(data.status) ? data.status : 'stopped'
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
    const title = presenter.getActivity(
      { ...data, status, input: record(data.input), facts: record(data.facts) },
      translate
    )
    if (typeof title !== 'string' || !title.trim()) return fallback
    return {
      ...fallback,
      title,
      icon: presenter.icon,
      group: !data.changes_data ? presenter.group : null,
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
    if (activity.group !== 'workspace') {
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
    group.status = ['running', 'failed', 'stopped', 'done'].find((status) =>
      group.lines.some((line) => line.status === status)
    )
    group.title = genericText(
      t,
      group.status === 'running'
        ? 'toolPresentation.workspaceRunning'
        : group.status === 'done'
          ? 'toolPresentation.workspaceDone'
          : 'toolPresentation.workspace',
      'Workspace activity'
    )
  }
  return groups
}
