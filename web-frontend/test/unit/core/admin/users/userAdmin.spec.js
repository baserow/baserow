import { TestApp } from '@baserow/test/helpers/testApp'
import UsersAdminTable from '@baserow/modules/core/components/admin/users/UsersAdminTable'
import UserForm from '@baserow/modules/core/components/admin/users/forms/UserForm'
import moment from '@baserow/modules/core/moment'
import flushPromises from 'flush-promises'
import UserAdminUserHelpers from '@baserow/test/helpers/userAdminHelpers'
import { MockServer } from '@baserow/test/fixtures/mockServer'

// Mock out debounce so we dont have to wait or simulate waiting for the various
// debounces in the search functionality.
jest.mock('lodash/debounce', () => jest.fn((fn) => fn))

describe('User Admin Component Tests', () => {
  let testApp = null
  let mockServer = null

  beforeAll(() => {
    testApp = new TestApp()
    mockServer = new MockServer(testApp.mock)
  })

  afterEach(() => testApp.afterEach())

  test('A users attributes will be displayed', async () => {
    const userSetup = {
      id: 1,
      username: 'user@baserow.io',
      name: 'user name',
      workspaces: [
        {
          id: 4,
          name: "users's workspace",
          permissions: 'ADMIN',
        },
        {
          id: 65,
          name: 'other_workspace',
        },
      ],
      lastLogin: '2021-04-26T07:50:45.6415059Z',
      dateJoined: '2021-04-21T12:04:27.379781Z',
      isActive: true,
      isStaff: true,
    }
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin(userSetup)

    const cells = ui.findCells()
    expect(cells.length).toBe(7)
    const {
      usernameCell,
      nameCell,
      workspacesCell,
      lastLoginCell,
      signedUpCell,
      isActiveCell,
    } = ui.getRow(cells, 0)

    // Username matches with correct initials and has an admin icon
    expect(usernameCell.text()).toContain(userSetup.username)
    expect(ui.usernameCellIsForStaffMember(usernameCell)).toBe(true)
    expect(ui.getUsernameInitials(usernameCell)).toBe('UN')

    // First name matches
    expect(nameCell.text()).toBe(userSetup.name)

    // Has two workspaces
    const workspaces = ui.getWorkspaces(workspacesCell)
    expect(workspaces.length).toBe(2)
    const firstWorkspace = workspaces.at(0)
    const secondWorkspace = workspaces.at(1)

    // The first workspace has the correct name and as the user is an admin an icon is
    // displayed
    expect(firstWorkspace.text()).toBe("users's workspace")
    expect(ui.workspaceCellShowsThisUserIsWorkspaceAdmin(firstWorkspace)).toBe(
      true
    )

    // The second workspace has the right name and no admin icon as the user is not an
    // admin
    expect(secondWorkspace.text()).toBe('other_workspace')
    expect(ui.workspaceCellShowsThisUserIsWorkspaceAdmin(secondWorkspace)).toBe(
      false
    )

    // The last login and signed up dates are correctly formatted to the locale
    moment.locale('nl')
    expect(lastLoginCell.text()).toMatch(/^04\/26\/2021 \d+:50 (AM|PM)$/)
    expect(signedUpCell.text()).toMatch(/^04\/21\/2021 \d+:04 (AM|PM)$/)

    // Shown as active
    expect(isActiveCell.text()).toBe('user.active')
  })

  test('A user with no workspaces is displayed without any', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      workspaces: [],
    })

    await flushPromises()

    const cells = ui.findCells()
    expect(cells.length).toBe(7)
    const { usernameCell, workspacesCell } = ui.getRow(cells, 0)

    expect(usernameCell.text()).toContain(user.username)
    const workspaces = ui.getWorkspaces(workspacesCell)
    expect(workspaces.length).toBe(0)
  })

  test.skip('A user can be deleted', async () => {
    // TODO: This test is skipped as it fails at
    // TypeError: Converting circular structure to JSON

    const { user, userAdmin, ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    expect(userAdmin.html()).toContain(user.username)

    const editUserContext = await ui.openFirstUserActionsMenu()
    await ui.clickDeleteUser(editUserContext)

    mockServer.expectUserDeleted(user.id)

    await ui.clickConfirmDeleteUserInModal()

    await flushPromises()

    expect(userAdmin.html()).not.toContain(user.username)
  })

  test('An active user can be deactivated', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      isActive: true,
    })

    const editUserContext = await ui.openFirstUserActionsMenu()

    mockServer.expectUserUpdated(user, {
      is_active: false,
    })

    await ui.clickDeactivateUser(editUserContext)

    await flushPromises()

    const cells = ui.findCells()
    const { isActiveCell } = ui.getRow(cells, 0)
    expect(isActiveCell.text()).toContain('user.deactivated')
  })

  test('A deactivated user can be activated', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      isActive: false,
    })

    const editUserContext = await ui.openFirstUserActionsMenu()

    mockServer.expectUserUpdated(user, {
      is_active: true,
    })

    await ui.clickActivateUser(editUserContext)

    await flushPromises()

    const cells = ui.findCells()
    const { isActiveCell } = ui.getRow(cells, 0)
    expect(isActiveCell.text()).toContain('user.active')
  })

  test('A users password can be changed', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const newValidPassword = '12345678'
    mockServer.expectUserUpdated(user, {
      password: newValidPassword,
    })

    await ui.changePassword(newValidPassword, newValidPassword)

    await flushPromises()
  })

  test('users password cant be changed if not entered the same twice', async () => {
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const validPassword = '1'.repeat(8)

    const errors = await ui.attemptToChangePasswordReturningModalError(
      validPassword,
      validPassword + 'DifferentFromFirst'
    )
    expect(errors.length).toBeGreaterThan(0)
    const error = errors.find((obj) => obj.$property === 'passwordConfirm')
    expect(error.$validator).toMatch('sameAsPassword')
  })

  test('users password cant be changed less than 8 characters', async () => {
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const tooShortPassword = '1'.repeat(7)

    const errors = await ui.attemptToChangePasswordReturningModalError(
      tooShortPassword,
      tooShortPassword
    )

    expect(errors.length).toBeGreaterThan(0)
    const error = errors.find((obj) => obj.$property === 'password')
    expect(error.$validator).toMatch('minLength')
  })

  test('users password cant be changed to more than 256 characters', async () => {
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const tooLongPassword = '1'.repeat(257)

    const errors = await ui.attemptToChangePasswordReturningModalError(
      tooLongPassword,
      tooLongPassword
    )

    expect(errors.length).toBeGreaterThan(0)
    const error = errors.find((obj) => obj.$property === 'password')
    expect(error.$validator).toMatch('maxLength')
  })

  test('users password can be changed to 256 characters', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const longestValidPassword = '1'.repeat(256)
    mockServer.expectUserUpdated(user, {
      password: longestValidPassword,
    })

    await ui.changePassword(longestValidPassword, longestValidPassword)

    await flushPromises()
  })

  test('changing a users password displays an error if the server responds with one', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const validPassword = '1'.repeat(8)

    testApp.dontFailOnErrorResponses()

    mockServer.expectUserUpdatedRespondsWithError(user, {
      error: 'SOME_ERROR',
      detail: 'Some error text',
    })

    const modal = await ui.changePassword(validPassword, validPassword)

    await flushPromises()

    expect(ui.getErrorText(modal)).toBe('clientHandler.notCompletedDescription')
  })

  test('a users full name can be changed', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      name: 'Old Full Name',
    })

    const newFullName = 'New Full Name'
    mockServer.expectUserUpdated(user, {
      name: newFullName,
      // Expect the other edit modal fields will be sent, just with no changes.
      is_staff: user.is_staff,
      is_active: user.is_active,
      username: user.username,
    })

    await ui.changeFullName(newFullName)

    await flushPromises()

    const cells = ui.findCells()
    const { nameCell } = ui.getRow(cells, 0)
    expect(nameCell.text()).toContain(newFullName)
  })

  test('when an server error is returned when editing a user it is shown', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({})

    testApp.dontFailOnErrorResponses()

    mockServer.expectUserUpdatedRespondsWithError(user, {
      error: 'SOME_ERROR',
      detail: 'Some error text',
    })

    const modal = await ui.changeFullName('some terrible value')

    await flushPromises()

    expect(ui.getErrorText(modal)).toBe('clientHandler.notCompletedDescription')
  })

  test('a users full name cant be changed to less than 2 characters', async () => {
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const tooShortFullName = '1'

    const editUserModal = await ui.changeFullName(tooShortFullName)
    const userFormComponent = editUserModal.findComponent(UserForm)
    expect(userFormComponent.vm.v$.values.name.minLength.$invalid).toBe(true)
  })

  test('a users full name cant be changed to more than 150 characters', async () => {
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const tooLongFullName = '1'.repeat(151)

    const editUserModal = await ui.changeFullName(tooLongFullName)
    const userFormComponent = editUserModal.findComponent(UserForm)
    expect(userFormComponent.vm.v$.values.name.maxLength.$invalid).toBe(true)
  })

  test('a users username be changed', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      username: 'oldusername@example.com',
    })

    const newUserName = 'new_email@example.com'
    mockServer.expectUserUpdated(user, {
      username: newUserName,
      // Expect the other edit modal fields will be sent, just with no changes.
      name: user.name,
      is_staff: user.is_staff,
      is_active: user.is_active,
    })

    await ui.changeEmail(newUserName)

    await flushPromises()

    const cells = ui.findCells()
    const { usernameCell } = ui.getRow(cells, 0)
    expect(usernameCell.text()).toContain(newUserName)
  })

  test('a users username cannot be changed to a invalid email address', async () => {
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    const invalidEmail = '1'

    const editUserModal = await ui.changeEmail(invalidEmail)
    const userFormComponent = editUserModal.findComponent(UserForm)
    expect(userFormComponent.vm.v$.values.username.email.$invalid).toBe(true)
  })

  test('changing a users username and closing without saving resets the modals form', async () => {
    const initialUsername = 'initial_username@gmail.com'
    const { ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      username: initialUsername,
    })

    const usernameEnteredButNotSaved = 'invalid'

    const editUserModal = await ui.changeEmail(usernameEnteredButNotSaved, {
      clickSave: false,
      exit: true,
    })

    const userFormComponent = editUserModal.findComponent(UserForm)
    expect(userFormComponent.vm.v$.values.username.$model).toBe(initialUsername)
  })
  test('a user can be set as staff ', async () => {
    await testToggleStaff(false)
  })

  test('a user can be unset as staff ', async () => {
    await testToggleStaff(true)
  })

  test('a user can be set as active ', async () => {
    await testToggleActive(false)
  })

  test('a user can be unset as active', async () => {
    await testToggleActive(true)
  })

  test('when there are fewer than 100 users the page buttons do nothing', async () => {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin()

    await ui.clickNextPage()
    await ui.clickNextPage()
    await ui.clickPrevPage()

    await flushPromises()

    expect(ui.getSingleRowUsernameText()).toContain(user.username)
  })

  test('when there are 2 pages of users the next and back buttons switch between them', async () => {
    const firstPageUser = mockServer.aUser({
      username: 'firstPageUser@example.com',
    })
    const secondPageUser = mockServer.aUser({
      username: 'secondPageUser@example.com',
    })
    mockServer.thereAreUsers([firstPageUser], 1, { count: 150 })
    mockServer.thereAreUsers([secondPageUser], 2, { count: 150 })

    const userAdmin = await testApp.mount(UsersAdminTable, {})
    const ui = new UserAdminUserHelpers(userAdmin)

    expect(ui.getSingleRowUsernameText()).toContain(firstPageUser.username)

    await ui.clickNextPage()
    await flushPromises()

    expect(ui.getSingleRowUsernameText()).toContain(secondPageUser.username)

    await ui.clickPrevPage()
    await flushPromises()

    expect(ui.getSingleRowUsernameText()).toContain(firstPageUser.username)
  })

  test('when not on the first page a sort will send the user back to the first page', async () => {
    const firstPageUser = mockServer.aUser({
      username: 'firstPageUser@example.com',
    })
    const secondPageUser = mockServer.aUser({
      username: 'secondPageUser@example.com',
    })
    mockServer.thereAreUsers([firstPageUser], 1, { count: 150 })
    mockServer.thereAreUsers([firstPageUser], 1, {
      count: 150,
      sorts: '+username',
    })
    mockServer.thereAreUsers([secondPageUser], 2, { count: 150 })

    const userAdmin = await testApp.mount(UsersAdminTable, {})
    const ui = new UserAdminUserHelpers(userAdmin)

    expect(ui.getSingleRowUsernameText()).toContain(firstPageUser.username)

    await ui.clickNextPage()
    await ui.clickUsernameHeader()

    expect(ui.getSingleRowUsernameText()).toContain(firstPageUser.username)
  })

  test('you can search by username which will pass the search text to the server', async () => {
    const firstUser = mockServer.aUser({
      id: 1,
      username: 'firstUser@example.com',
    })
    const secondUser = mockServer.aUser({
      id: 2,
      username: 'secondUser@example.com',
    })
    mockServer.thereAreUsers([firstUser, secondUser], 1)
    mockServer.thereAreUsers([firstUser], 1, { search: 'firstUser' })

    const userAdmin = await testApp.mount(UsersAdminTable, {})
    const ui = new UserAdminUserHelpers(userAdmin)

    const cells = ui.findCells(14)
    const { usernameCell: firstUsernameCell } = ui.getRow(cells, 0)
    expect(firstUsernameCell.text()).toContain('firstUser@example.com')
    const { usernameCell: secondUsernameCell } = ui.getRow(cells, 1)
    expect(secondUsernameCell.text()).toContain('secondUser@example.com')

    await ui.typeIntoSearchBox('firstUser')
    await flushPromises()

    expect(ui.getSingleRowUsernameText()).toContain(firstUser.username)
  })

  test('searching and then sorting will preserve the search', async () => {
    const firstUser = mockServer.aUser({
      id: 1,
      username: 'firstUser@example.com',
    })
    const secondUser = mockServer.aUser({
      id: 2,
      username: 'secondUser@example.com',
    })
    mockServer.thereAreUsers([firstUser, secondUser], 1)
    mockServer.thereAreUsers([firstUser], 1, { search: 'firstUser' })
    mockServer.thereAreUsers([firstUser], 1, {
      search: 'firstUser',
      sorts: '+username',
    })

    const userAdmin = await testApp.mount(UsersAdminTable, {})
    const ui = new UserAdminUserHelpers(userAdmin)

    const cells = ui.findCells(14)
    const { usernameCell: firstUsernameCell } = ui.getRow(cells, 0)
    expect(firstUsernameCell.text()).toContain('firstUser@example.com')
    const { usernameCell: secondUsernameCell } = ui.getRow(cells, 1)
    expect(secondUsernameCell.text()).toContain('secondUser@example.com')

    await ui.typeIntoSearchBox('firstUser')
    await flushPromises()

    expect(ui.getSingleRowUsernameText()).toContain(firstUser.username)

    await ui.clickUsernameHeader()
    await flushPromises()

    expect(ui.getSingleRowUsernameText()).toContain(firstUser.username)
  })

  test('you can sort by multiple columns which will pass the sorts to the server', async () => {
    const first = 'firstUser@example.com'
    const second = 'secondUser@example.com'
    const third = 'thirdUser@example.com'
    const firstUser = mockServer.aUser({
      id: 1,
      username: first,
    })
    const secondUser = mockServer.aUser({
      id: 2,
      username: second,
    })
    const thirdUser = mockServer.aUser({
      id: 3,
      username: third,
    })
    mockServer.thereAreUsers([firstUser, secondUser, thirdUser], 1)

    const userAdmin = await testApp.mount(UsersAdminTable, {})
    const ui = new UserAdminUserHelpers(userAdmin)

    let usernameCellsText = ui.findUsernameColumnCellsText()
    expect(usernameCellsText).toStrictEqual([first, second, third])

    // Clicking once starts with a descending sort
    mockServer.thereAreUsers([secondUser, firstUser, thirdUser], 1, {
      sorts: '+username',
    })
    await ui.clickUsernameHeader()
    await flushPromises()
    usernameCellsText = ui.findUsernameColumnCellsText()
    expect(usernameCellsText).toStrictEqual([second, first, third])

    // Clicking again toggles to a ascending sort
    mockServer.thereAreUsers([thirdUser, firstUser, secondUser], 1, {
      sorts: '-username',
    })
    await ui.clickUsernameHeader()
    await flushPromises()
    usernameCellsText = ui.findUsernameColumnCellsText()
    expect(usernameCellsText).toStrictEqual([third, first, second])

    // Clicking again turns off the sort
    await ui.clickUsernameHeader()
    await flushPromises()
    usernameCellsText = ui.findUsernameColumnCellsText()
    expect(usernameCellsText).toStrictEqual([first, second, third])

    // Can click multiple columns resulting in an ordered sort
    mockServer.thereAreUsers([firstUser, thirdUser, secondUser], 1, {
      sorts: '-username,+name',
    })
    await ui.clickUsernameHeader()
    await ui.clickUsernameHeader()
    await ui.clickFullnameHeader()
    await flushPromises()
    usernameCellsText = ui.findUsernameColumnCellsText()
    expect(usernameCellsText).toStrictEqual([first, third, second])
  })

  async function testToggleStaff(startingIsStaff) {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      isStaff: startingIsStaff,
    })

    let cells = ui.findCells()
    const { usernameCell } = ui.getRow(cells, 0)
    expect(ui.usernameCellIsForStaffMember(usernameCell)).toBe(startingIsStaff)

    mockServer.expectUserUpdated(user, {
      is_staff: !startingIsStaff,
      // Expect the other edit modal fields will be sent, just with no changes.
      username: user.username,
      name: user.name,
      is_active: user.is_active,
    })

    await ui.toggleIsStaff()

    await flushPromises()

    cells = ui.findCells()
    const { usernameCell: updatedUsernameCell } = ui.getRow(cells, 0)
    expect(ui.usernameCellIsForStaffMember(updatedUsernameCell)).toBe(
      !startingIsStaff
    )
  }

  async function testToggleActive(startingIsActive) {
    const { user, ui } = await whenThereIsAUserAndYouOpenUserAdmin({
      isActive: startingIsActive,
    })

    let cells = ui.findCells()
    const { isActiveCell } = ui.getRow(cells, 0)
    expect(isActiveCell.text()).toBe(
      startingIsActive ? 'user.active' : 'user.deactivated'
    )

    mockServer.expectUserUpdated(user, {
      is_active: !startingIsActive,
      // Expect the other edit modal fields will be sent, just with no changes.
      username: user.username,
      name: user.name,
      is_staff: user.is_staff,
    })

    await ui.toggleIsActive()

    await flushPromises()

    cells = ui.findCells()
    const { isActiveCell: updatedIsActiveCell } = ui.getRow(cells, 0)
    expect(updatedIsActiveCell.text()).toBe(
      startingIsActive ? 'user.deactivated' : 'user.active'
    )
  }

  async function whenThereIsAUserAndYouOpenUserAdmin(userSetup = {}) {
    const user = mockServer.aUser(userSetup)
    mockServer.thereAreUsers([user], 1)

    const userAdmin = await testApp.mount(UsersAdminTable, {})
    const ui = new UserAdminUserHelpers(userAdmin)
    return { user, userAdmin, ui }
  }
})
