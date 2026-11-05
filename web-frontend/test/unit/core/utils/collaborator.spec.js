import { getCollaboratorName } from '@baserow/modules/core/utils/collaborator'

it('uses cached Agent names without resolving their Subject ID as a User', () => {
  const getUser = vi.fn(() => ({ name: 'Unrelated human' }))
  const store = {
    getters: {
      'workspace/getAll': [{}],
      'workspace/getUserById': getUser,
    },
  }
  expect(
    getCollaboratorName({ id: 5, name: 'Assistant', type: 'core.Agent' }, store)
  ).toBe('Assistant')
  expect(getUser).not.toHaveBeenCalled()
})

it('keeps retained names and reflects live human renames', () => {
  const store = {
    getters: {
      'workspace/getAll': [{}],
      'workspace/getUserById': (id) =>
        id === 1 ? { name: 'Renamed human' } : undefined,
    },
  }
  expect(
    getCollaboratorName({ id: 1, name: 'Old name', type: 'auth.User' }, store)
  ).toBe('Renamed human')
  expect(
    getCollaboratorName(
      { id: 2, name: 'Retained human', type: 'auth.User' },
      store
    )
  ).toBe('Retained human')
})

it('delegates identity display to a registered SubjectType', () => {
  const subject = { id: 10, type: 'test.External', name: 'External identity' }
  const type = { getDisplayName: vi.fn((value) => `External: ${value.name}`) }
  const registry = {
    exists: (namespace, name) =>
      namespace === 'subject' && name === subject.type,
    get: () => type,
  }
  expect(getCollaboratorName(subject, {}, registry)).toBe(
    'External: External identity'
  )
  expect(type.getDisplayName).toHaveBeenCalledWith(subject, expect.any(Object))
})
