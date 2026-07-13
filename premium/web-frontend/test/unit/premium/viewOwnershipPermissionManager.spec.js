import { ViewOwnershipPermissionManagerType } from '@baserow_premium/permissionManagerTypes'

function createManager(userId) {
  const manager = new ViewOwnershipPermissionManagerType()
  manager.app = {
    $store: {
      getters: {
        'auth/getUserId': userId,
      },
    },
  }
  return manager
}

function personalView(ownerId) {
  return { ownership_type: 'personal', owned_by_id: ownerId }
}

function collaborativeView() {
  return { ownership_type: 'collaborative' }
}

const ALL_ALLOWED_OPERATIONS = [
  'database.table.view.create_filter',
  'database.table.view.create_sort',
  'database.table.view.create_decoration',
  'database.table.view.sort.update',
  'database.table.view.sort.delete',
  'database.table.view.update_field_options',
  'database.table.view.update',
  'database.table.view.delete',
  'database.table.view.duplicate',
  'database.table.view.filter.update',
  'database.table.view.filter.delete',
  'database.table.view.decoration.update',
  'database.table.view.decoration.delete',
  'database.table.view.update_default_values',
  'database.table.view.create_group_by',
  'database.table.view.group_by.update',
  'database.table.view.group_by.delete',
  'database.table.view.prioritize_sortings',
  'database.table.view.prioritize_group_bys',
  'database.table.view.create_filter_group',
  'database.table.view.filter_group.update',
  'database.table.view.filter_group.delete',
]

describe('ViewOwnershipPermissionManagerType', () => {
  describe('personal view owned by current user', () => {
    it.each(ALL_ALLOWED_OPERATIONS)('allows %s', (operation) => {
      const manager = createManager(42)
      const result = manager.hasPermission(null, operation, personalView(42), 1)
      expect(result).toBe(true)
    })
  })

  describe('personal view owned by different user', () => {
    it.each(ALL_ALLOWED_OPERATIONS)('denies %s', (operation) => {
      const manager = createManager(42)
      const result = manager.hasPermission(null, operation, personalView(99), 1)
      expect(result).toBe(false)
    })
  })

  describe('collaborative view', () => {
    it.each(ALL_ALLOWED_OPERATIONS)(
      'does not handle %s (falls through)',
      (operation) => {
        const manager = createManager(42)
        const result = manager.hasPermission(
          null,
          operation,
          collaborativeView(),
          1
        )
        expect(result).toBeUndefined()
      }
    )
  })

  describe('unknown operation', () => {
    it('does not handle operations outside the allowlist', () => {
      const manager = createManager(42)
      const result = manager.hasPermission(
        null,
        'database.table.view.some_unknown_op',
        personalView(42),
        1
      )
      expect(result).toBeUndefined()
    })
  })

  describe('group by operations are included (regression)', () => {
    const groupByOps = [
      'database.table.view.create_group_by',
      'database.table.view.group_by.update',
      'database.table.view.group_by.delete',
      'database.table.view.prioritize_group_bys',
    ]

    it.each(groupByOps)(
      '%s is allowed for personal view owner',
      (operation) => {
        const manager = createManager(10)
        expect(
          manager.hasPermission(null, operation, personalView(10), 1)
        ).toBe(true)
      }
    )
  })

  describe('sort and filter operations have matching group by counterparts', () => {
    const sortOps = [
      'database.table.view.create_sort',
      'database.table.view.sort.update',
      'database.table.view.sort.delete',
      'database.table.view.prioritize_sortings',
    ]
    const groupByOps = [
      'database.table.view.create_group_by',
      'database.table.view.group_by.update',
      'database.table.view.group_by.delete',
      'database.table.view.prioritize_group_bys',
    ]

    it('every sort operation pattern has a group by equivalent', () => {
      const manager = createManager(1)
      const view = personalView(1)

      for (let i = 0; i < sortOps.length; i++) {
        const sortResult = manager.hasPermission(null, sortOps[i], view, 1)
        const groupByResult = manager.hasPermission(
          null,
          groupByOps[i],
          view,
          1
        )
        expect(groupByResult).toBe(sortResult)
      }
    })
  })
})
