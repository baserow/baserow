import { describe, expect, test, vi } from 'vitest'

import AuditLogService from '@baserow_enterprise/services/auditLog'

describe('audit log service', () => {
  test('fetchActors uses the dedicated audit log actor endpoint', () => {
    const client = { get: vi.fn() }

    AuditLogService(client).fetchActors(2, 'robot', 5)

    expect(client.get).toHaveBeenCalledWith('/audit-log/actors/', {
      params: { page: 2, search: 'robot', workspace_id: 5 },
    })
  })
})
