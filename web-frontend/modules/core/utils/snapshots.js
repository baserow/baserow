/**
 * Helpers for the snapshot keep of an application: how many snapshots it keeps,
 * and which ones go when it takes a new one or its keep is lowered. They mirror
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
 * snapshots keeps `keep` of them: its oldest unprotected ones beyond the keep.
 * Protected snapshots are never deleted, but still count towards the keep.
 */
export function getSnapshotsToDelete(snapshots, keep) {
  const excess = snapshots.length - keep
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
 * provided snapshots keeps `keep` of them, or `null` when it replaces none.
 */
export function getSnapshotToReplace(snapshots, keep) {
  if (keep <= 0 || snapshots.length < keep) {
    return null
  }
  return getSnapshotsToDelete(snapshots, keep - 1)[0] || null
}

/**
 * Returns whether an application holding the provided snapshots has room for a
 * new one: `none` when it keeps no snapshots, `protected` when it's at its keep
 * and every snapshot it holds is protected, otherwise `ok`.
 */
export function getSnapshotRoom(snapshots, keep) {
  if (keep <= 0) {
    return 'none'
  }
  if (snapshots.length < keep) {
    return 'ok'
  }
  return getSnapshotToReplace(snapshots, keep) ? 'ok' : 'protected'
}

/**
 * Counts how many snapshots lowering the keep of applications deletes, given how
 * many snapshots each holds and how many of them are protected.
 *
 * @param {Array<{snapshotCount: number, protectedCount: number}>} applications
 * @param {number} keep The new keep of every one of them.
 */
export function countSnapshotsDeletedByKeep(applications, keep) {
  return applications.reduce((total, { snapshotCount, protectedCount }) => {
    const excess = snapshotCount - keep
    const unprotected = snapshotCount - protectedCount
    return total + Math.max(0, Math.min(excess, unprotected))
  }, 0)
}

/**
 * Returns whether raising keeps from `used` to `newUsed` reserved snapshots takes
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
 * Validates a new keep, the way the backend does, and returns the translation key
 * of the problem, or `null` when it's valid.
 *
 * @param {object} values
 * @param {number} values.keep The new keep.
 * @param {number} values.originalKeep The keep before the change.
 * @param {number} values.used How much of the allowance is reserved now.
 * @param {number} values.newUsed How much would be reserved after the change.
 * @param {number|null} values.limit The allowance, `null` without a limit.
 * @param {number|null} values.maxKeep The maximum keep, `null` without one.
 * @param {number} values.protectedCount The most protected snapshots one of the
 *   affected applications holds.
 * @param {boolean} values.canExceedAllowance Whether a keep can go over the
 *   allowance, which then only warns.
 */
export function validateSnapshotKeep({
  keep,
  originalKeep,
  used,
  newUsed,
  limit,
  maxKeep,
  protectedCount,
  canExceedAllowance = false,
}) {
  if (!Number.isInteger(keep) || keep < 0) {
    return 'snapshotKeep.errorInvalid'
  }
  if (maxKeep !== null && keep > maxKeep && keep > originalKeep) {
    return 'snapshotKeep.errorAboveMaximum'
  }
  if (
    !canExceedAllowance &&
    goesOverSnapshotAllowance({ used, newUsed, limit })
  ) {
    return 'snapshotKeep.errorExceedsAllowance'
  }
  if (keep < protectedCount) {
    return 'snapshotKeep.errorBelowProtected'
  }
  return null
}

/**
 * When the backend refuses a keep change because it deletes snapshots that the
 * local list didn't predict, returns how many it deletes. Otherwise `null`.
 *
 * @param {Error} error The error of the request.
 */
export function getSnapshotsDeletedByKeepError(error) {
  const data = error?.response?.data
  if (data?.error !== 'ERROR_SNAPSHOT_KEEP_CHANGE_DELETES_SNAPSHOTS') {
    return null
  }
  const match = /(\d+)/.exec(String(data.detail || ''))
  return match ? parseInt(match[1], 10) : 1
}
