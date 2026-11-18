import {
  countSnapshotsDeletedByKeep,
  getSnapshotRoom,
  getSnapshotsToDelete,
  getSnapshotToReplace,
  validateSnapshotKeep,
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

describe('snapshot keep utils', () => {
  test('lowering a keep deletes the oldest unprotected snapshots', () => {
    expect(getSnapshotsToDelete(snapshots, 4)).toEqual([])
    expect(getSnapshotsToDelete(snapshots, 2).map(({ id }) => id)).toEqual([
      1, 2,
    ])
    // Protected snapshots are never deleted, even when the keep is lower.
    expect(getSnapshotsToDelete(snapshots, 0).map(({ id }) => id)).toEqual([
      1, 2, 4,
    ])
  })

  test('a new snapshot replaces the oldest unprotected one at the keep', () => {
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

  test('counts the snapshots lowering a default keep deletes', () => {
    expect(
      countSnapshotsDeletedByKeep(
        [
          { snapshotCount: 3, protectedCount: 1 },
          { snapshotCount: 3, protectedCount: 3 },
          { snapshotCount: 1, protectedCount: 0 },
        ],
        1
      )
    ).toBe(2)
  })

  test('validates a keep like the backend', () => {
    const values = {
      keep: 3,
      originalKeep: 2,
      used: 8,
      newUsed: 9,
      limit: 10,
      maxKeep: null,
      protectedCount: 0,
    }
    expect(validateSnapshotKeep(values)).toBeNull()
    expect(validateSnapshotKeep({ ...values, keep: -1 })).toBe(
      'snapshotKeep.errorInvalid'
    )
    expect(validateSnapshotKeep({ ...values, newUsed: 11 })).toBe(
      'snapshotKeep.errorExceedsAllowance'
    )
    // Unless the workspace can go over it.
    expect(
      validateSnapshotKeep({ ...values, newUsed: 11, canExceedAllowance: true })
    ).toBeNull()
    // Lowering is allowed while over the allowance.
    expect(
      validateSnapshotKeep({ ...values, keep: 1, used: 12, newUsed: 11 })
    ).toBeNull()
    expect(validateSnapshotKeep({ ...values, maxKeep: 2 })).toBe(
      'snapshotKeep.errorAboveMaximum'
    )
    expect(validateSnapshotKeep({ ...values, protectedCount: 4 })).toBe(
      'snapshotKeep.errorBelowProtected'
    )
  })
})
