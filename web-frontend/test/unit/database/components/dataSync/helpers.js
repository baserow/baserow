export function createSyncJob(values) {
  return {
    type: 'sync_data_sync_table',
    progress_percentage: 100,
    human_readable_error: '',
    created_on: '2026-07-10T10:00:00Z',
    updated_on: '2026-07-10T10:00:30Z',
    triggered_by: 'manual',
    user_name: 'John',
    data_sync: { id: 42 },
    ...values,
  }
}
