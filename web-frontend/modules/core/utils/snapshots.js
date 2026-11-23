/**
 * Helpers for the max snapshots of an application: how many snapshots it keeps,
 * and which ones go when it takes a new one or its max snapshots is lowered. They mirror
 * the backend rules, so the modal can say what happens before it happens. The
 * backend still checks everything.
 */

function byOldestFirst(a, b) {
  return (
    new Date(a.created_at) - new Date(b.created_at) || (a.id || 0) - (b.id || 0)
  )
}

/**
 * Returns the snapshots that are deleted when an application holding the provided
 * snapshots keeps `maxSnapshots` of them: its oldest unprotected ones beyond the max snapshots.
 * Protected snapshots are never deleted, but still count towards the max snapshots.
 */
export function getSnapshotsToDelete(snapshots, maxSnapshots) {
  const excess = snapshots.length - maxSnapshots
  if (excess <= 0) {
    return []
  }
  return snapshots
    .filter((snapshot) => !snapshot.protected)
    .sort(byOldestFirst)
    .slice(0, excess)
}

/**
 * Returns the snapshot a new snapshot replaces when an application holding the
 * provided snapshots keeps `maxSnapshots` of them, or `null` when it replaces none.
 */
export function getSnapshotToReplace(snapshots, maxSnapshots) {
  if (maxSnapshots <= 0 || snapshots.length < maxSnapshots) {
    return null
  }
  return getSnapshotsToDelete(snapshots, maxSnapshots - 1)[0] || null
}

/**
 * Returns whether an application holding the provided snapshots has room for a
 * new one: `none` when it keeps no snapshots, `protected` when it's at its max snapshots
 * and every snapshot it holds is protected, otherwise `ok`.
 */
export function getSnapshotRoom(snapshots, maxSnapshots) {
  if (maxSnapshots <= 0) {
    return 'none'
  }
  if (snapshots.length < maxSnapshots) {
    return 'ok'
  }
  return getSnapshotToReplace(snapshots, maxSnapshots) ? 'ok' : 'protected'
}

/**
 * Counts how many snapshots lowering the max snapshots of applications deletes, given how
 * many snapshots each holds and how many of them are protected.
 *
 * @param {Array<{snapshotCount: number, protectedCount: number}>} applications
 * @param {number} maxSnapshots The new max snapshots of every one of them.
 */
export function countSnapshotsDeletedByMaxSnapshots(
  applications,
  maxSnapshots
) {
  return applications.reduce((total, { snapshotCount, protectedCount }) => {
    const excess = snapshotCount - maxSnapshots
    const unprotected = snapshotCount - protectedCount
    return total + Math.max(0, Math.min(excess, unprotected))
  }, 0)
}

/**
 * Returns whether raising max snapshots from `used` to `newUsed` reserved snapshots takes
 * the workspace over its allowance, or further over it.
 *
 * @param {object} values
 * @param {number} values.used How much of the allowance is reserved now.
 * @param {number} values.newUsed How much would be reserved after the change.
 * @param {number|null} values.limit The allowance, `null` without a limit.
 */
export function goesOverSnapshotAllowance({ used, newUsed, limit }) {
  return limit !== null && newUsed > used && newUsed > limit
}

/**
 * Validates a new max snapshots, the way the backend does, and returns the translation key
 * of the problem, or `null` when it's valid.
 *
 * @param {object} values
 * @param {number} values.maxSnapshots The new max snapshots.
 * @param {number} values.originalMaxSnapshots The max snapshots before the change.
 * @param {number} values.used How much of the allowance is reserved now.
 * @param {number} values.newUsed How much would be reserved after the change.
 * @param {number|null} values.limit The allowance, `null` without a limit.
 * @param {number|null} values.maxSnapshotsLimit The max snapshots limit, `null` without one.
 * @param {number} values.protectedCount The most protected snapshots one of the
 *   affected applications holds.
 * @param {boolean} values.canExceedAllowance Whether a max can go over the
 *   allowance, which then only warns.
 */
export function validateMaxSnapshots({
  maxSnapshots,
  originalMaxSnapshots,
  used,
  newUsed,
  limit,
  maxSnapshotsLimit,
  protectedCount,
  canExceedAllowance = false,
}) {
  if (!Number.isInteger(maxSnapshots) || maxSnapshots < 0) {
    return 'maxSnapshots.errorInvalid'
  }
  if (
    maxSnapshotsLimit !== null &&
    maxSnapshots > maxSnapshotsLimit &&
    maxSnapshots > originalMaxSnapshots
  ) {
    return 'maxSnapshots.errorAboveMaximum'
  }
  if (
    !canExceedAllowance &&
    goesOverSnapshotAllowance({ used, newUsed, limit })
  ) {
    return 'maxSnapshots.errorExceedsAllowance'
  }
  if (maxSnapshots < protectedCount) {
    return 'maxSnapshots.errorBelowProtected'
  }
  return null
}

/**
 * When the backend refuses a max change because it deletes snapshots that the
 * local list didn't predict, returns how many it deletes. Otherwise `null`.
 *
 * @param {Error} error The error of the request.
 */
export function getSnapshotsDeletedByMaxSnapshotsError(error) {
  const data = error?.response?.data
  if (data?.error !== 'ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS') {
    return null
  }
  const match = /(\d+)/.exec(String(data.detail || ''))
  return match ? parseInt(match[1], 10) : 1
}

// The errors a snapshot creation gets when the snapshots modal shows out of date
// snapshots or max snapshots.
const OUT_OF_DATE_SNAPSHOT_ERRORS = [
  'ERROR_MAXIMUM_SNAPSHOTS_REACHED',
  'ERROR_MAX_SNAPSHOTS_IS_ZERO',
  'ERROR_MAX_SNAPSHOTS_FULL_OF_PROTECTED',
  'ERROR_MAX_SNAPSHOTS_EXCEEDS_ALLOWANCE',
  'ERROR_SNAPSHOT_IS_BEING_CREATED',
]

/**
 * Whether the error of a snapshot creation means that the snapshots or the max
 * snapshots the modal shows are out of date.
 *
 * @param {Error} error The error of the request.
 */
export function isOutOfDateSnapshotsError(error) {
  return OUT_OF_DATE_SNAPSHOT_ERRORS.includes(error?.response?.data?.error)
}

/**
 * Whether the error of an action on a snapshot means that the snapshot no longer
 * exists, for example because a newer snapshot replaced it.
 *
 * @param {Error} error The error of the request.
 */
export function isSnapshotGoneError(error) {
  return error?.response?.data?.error === 'ERROR_SNAPSHOT_DOES_NOT_EXIST'
}
