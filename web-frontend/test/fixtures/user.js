export function aUser({
  id = 1,
  username = 'user@baserow.io',
  name = 'user_name',
  workspaces = [
    {
      id: 1,
      name: 'some_workspace',
      permissions: 'ADMIN',
    },
  ],
  lastLogin = '2021-04-26T07:50:45.643059Z',
  dateJoined = '2021-04-21T12:04:27.379781Z',
  isActive = true,
  isStaff = true,
}) {
  return {
    id,
    username,
    name,
    workspaces,
    last_login: lastLogin,
    date_joined: dateJoined,
    is_active: isActive,
    is_staff: isStaff,
  }
}

export function createUsersForAdmin(
  mock,
  users,
  page,
  { count = null, search = null, sorts = null }
) {
  const params = { page }
  if (search !== null) {
    params.search = search
  }
  if (sorts !== null) {
    params.sorts = sorts
  }
  mock.onGet(`/admin/users/`, { params }).reply(200, {
    count: count === null ? users.length : count,
    results: users,
  })
}

export function expectUserDeleted(mock, userId) {
  mock.onDelete(`/admin/users/${userId}/`).reply(200)
}

export function expectUserUpdated(mock, user, changes) {
  mock
    .onPatch(new RegExp(`/admin/users/${user.id}/`))
    .reply(200, Object.assign({}, user, changes))
}

export function expectUserUpdatedRespondsWithError(mock, user, error) {
  mock.onPatch(`/admin/users/${user.id}/`).reply(500, error)
}
