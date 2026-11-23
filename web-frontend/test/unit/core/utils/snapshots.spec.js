import {
  countSnapshotsDeletedByMaxSnapshots,
  getSnapshotRoom,
  getSnapshotsToDelete,
  getSnapshotToReplace,
  validateMaxSnapshots,
} from '@baserow/modules/core/utils/snapshots'

const snapshot = (id, day, isProtected) => ({
  id,
  created_at: `2026-11-${String(day).padStart(2, '0')}T10:00:00Z`,
  protected: isProtected,
})

// Newest first, as the API lists them.
const snapshots = [
  snapshot(4, 4, false),
  snapshot(3, 3, true),
  snapshot(2, 2, false),
  snapshot(1, 1, false),
]

describe('max snapshots utils', () => {
  test('lowering a max deletes the oldest unprotected snapshots', () => {
    expect(getSnapshotsToDelete(snapshots, 4)).toEqual([])
    expect(getSnapshotsToDelete(snapshots, 2).map(({ id }) => id)).toEqual([
      1, 2,
    ])
    // Protected snapshots are never deleted, even when the max snapshots is lower.
    expect(getSnapshotsToDelete(snapshots, 0).map(({ id }) => id)).toEqual([
      1, 2, 4,
    ])
  })

  test('a new snapshot replaces the oldest unprotected one at the max snapshots', () => {
    expect(getSnapshotToReplace(snapshots, 5)).toBeNull()
    expect(getSnapshotToReplace(snapshots, 4).id).toBe(1)
    expect(getSnapshotToReplace(snapshots, 0)).toBeNull()
  })

  test('tells whether there is room for a new snapshot', () => {
    expect(getSnapshotRoom(snapshots, 0)).toBe('none')
    expect(getSnapshotRoom(snapshots, 5)).toBe('ok')
    expect(getSnapshotRoom(snapshots, 4)).toBe('ok')
    expect(getSnapshotRoom([snapshot(1, 1, true)], 1)).toBe('protected')
  })

  test('counts the snapshots lowering a default max snapshots deletes', () => {
    expect(
      countSnapshotsDeletedByMaxSnapshots(
        [
          { snapshotCount: 3, protectedCount: 1 },
          { snapshotCount: 3, protectedCount: 3 },
          { snapshotCount: 1, protectedCount: 0 },
        ],
        1
      )
    ).toBe(2)
  })

  test('validates a max like the backend', () => {
    const values = {
      maxSnapshots: 3,
      originalMaxSnapshots: 2,
      used: 8,
      newUsed: 9,
      limit: 10,
      maxSnapshotsLimit: null,
      protectedCount: 0,
    }
    expect(validateMaxSnapshots(values)).toBeNull()
    expect(validateMaxSnapshots({ ...values, maxSnapshots: -1 })).toBe(
      'maxSnapshots.errorInvalid'
    )
    expect(validateMaxSnapshots({ ...values, newUsed: 11 })).toBe(
      'maxSnapshots.errorExceedsAllowance'
    )
    // Unless the workspace can go over it.
    expect(
      validateMaxSnapshots({ ...values, newUsed: 11, canExceedAllowance: true })
    ).toBeNull()
    // Lowering is allowed while over the allowance.
    expect(
      validateMaxSnapshots({
        ...values,
        maxSnapshots: 1,
        used: 12,
        newUsed: 11,
      })
    ).toBeNull()
    expect(validateMaxSnapshots({ ...values, maxSnapshotsLimit: 2 })).toBe(
      'maxSnapshots.errorAboveMaximum'
    )
    expect(validateMaxSnapshots({ ...values, protectedCount: 4 })).toBe(
      'maxSnapshots.errorBelowProtected'
    )
  })
})
