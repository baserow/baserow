import EditUserContext from '@baserow/modules/core/components/admin/users/contexts/EditUserContext'
import Error from '@baserow/modules/core/components/Error'
import ChangeUserPasswordModal from '@baserow/modules/core/components/admin/users/modals/ChangeUserPasswordModal'
import ChangePasswordForm from '@baserow/modules/core/components/admin/users/forms/ChangePasswordForm'
import EditUserModal from '@baserow/modules/core/components/admin/users/modals/EditUserModal'
import CrudTableSearch from '@baserow/modules/core/components/crudTable/CrudTableSearch'
import DeleteUserModal from '@baserow/modules/core/components/admin/users/modals/DeleteUserModal'
export default class UserAdminUserHelpers {
  constructor(userAdminComponent) {
    this.c = userAdminComponent
  }

  findCells(numCellsExpected = 7) {
    const cells = this.c.findAll('tbody .data-table__table-cell-content')
    expect(cells.length).toBe(numCellsExpected)
    return cells
  }

  findUsernameColumnCellsText() {
    const cells = this.c.findAll('tbody .data-table__table-cell-content')
    const usernameCells = []
    const numRows = cells.length / 7
    for (let i = 0; i < numRows; i++) {
      usernameCells.push(
        cells
          .at(i * 7 + 0)
          .find('.user-admin-username__name')
          .text()
      )
    }
    return usernameCells
  }

  getRow(cells, rowNumber) {
    const offset = rowNumber * 7
    return {
      usernameCell: cells.at(offset),
      nameCell: cells.at(offset + 1),
      workspacesCell: cells.at(offset + 2),
      lastLoginCell: cells.at(offset + 3),
      signedUpCell: cells.at(offset + 4),
      isActiveCell: cells.at(offset + 5),
      moreCell: cells.at(offset + 6),
    }
  }

  getSingleRowUsernameText() {
    const cells = this.findCells()
    const { usernameCell } = this.getRow(cells, 0)
    return usernameCell.text()
  }

  getUsernameInitials(usernameCell) {
    const initials = usernameCell.get('.user-admin-username__avatar')
    return initials.text()
  }

  usernameCellIsForStaffMember(usernameCell) {
    return usernameCell.find('.user-admin-username__icon').exists()
  }

  getWorkspaces(workspacesCell) {
    return workspacesCell.findAll('.expand-overflow-list__item')
  }

  workspaceCellShowsThisUserIsWorkspaceAdmin(workspaceCell) {
    return workspaceCell.find('.user-admin-group__icon').exists()
  }

  async openFirstUserActionsMenu() {
    await this.c.get('.data-table__more').trigger('click')
    return this.c.findComponent(EditUserContext)
  }

  clickDeleteUser(editUserContext) {
    return editUserContext.find('.iconoir-bin').trigger('click')
  }

  clickDeactivateUser(editUserContext) {
    return editUserContext.find('.iconoir-cancel').trigger('click')
  }

  clickActivateUser(editUserContext) {
    return editUserContext.find('.iconoir-check').trigger('click')
  }

  clickEditUser(editUserContext) {
    return editUserContext.find('.iconoir-edit-pencil').trigger('click')
  }

  clickChangeUserPassword(editUserContext) {
    return editUserContext.find('.iconoir-key-alt').trigger('click')
  }

  async attemptToChangePasswordReturningModalError(password, repeatPassword) {
    const changePasswordModal = await this.changePassword(
      password,
      repeatPassword
    )

    const wrapper = changePasswordModal.findComponent(ChangePasswordForm)
    return wrapper.vm.v$.values.$errors
  }

  getModalFieldErrorText(modal) {
    // return modalMounted
    //   .find('.control__messages--error')
    //   .text()
    //   .replace(/\n/gm, '')
    //   .replace(/\s\s+/g, ' ')
  }

  async changePassword(password, repeatPassword) {
    const editUserContext = await this.openFirstUserActionsMenu()

    await this.clickChangeUserPassword(editUserContext)

    const changePasswordModal = this.c.findComponent(ChangeUserPasswordModal)
    const passwordInputs = changePasswordModal.findAll('input')

    passwordInputs.at(0).element.value = password
    await passwordInputs.at(0).trigger('input')
    passwordInputs.at(1).element.value = repeatPassword
    await passwordInputs.at(1).trigger('input')

    await changePasswordModal.find('button').trigger('click')

    return changePasswordModal
  }

  getErrorText(component) {
    return component.findComponent(Error).find('.alert__message').text()
  }

  changeFullName(newFullName, options = {}) {
    return this.changeUserEditField(newFullName, 0, options)
  }

  async getUserEditModalEmailField() {
    const editUserContext = await this.openFirstUserActionsMenu()

    await this.clickEditUser(editUserContext)

    const editUserModal = this.c.findComponent(EditUserModal)
    const userEditInputs = editUserModal.findAll('input')

    return userEditInputs.at(1)
  }

  async changeUserEditField(
    newValue,
    inputIndex,
    { clickSave = true, exit = false } = {}
  ) {
    const editUserContext = await this.openFirstUserActionsMenu()

    await this.clickEditUser(editUserContext)

    const editUserModal = this.c.findComponent(EditUserModal)
    const userEditInputs = editUserModal.findAll('input')

    userEditInputs.at(inputIndex).element.value = newValue
    await userEditInputs.at(inputIndex).trigger('input')

    await editUserModal.find('button').trigger('click')

    if (exit) {
      await editUserModal.find('.modal__close').trigger('click')
    }

    return editUserModal
  }

  async changeUserCheckbox(checkboxIndex) {
    const editUserContext = await this.openFirstUserActionsMenu()

    await this.clickEditUser(editUserContext)

    const editUserModal = this.c.findComponent(EditUserModal)
    const checkboxes = editUserModal.findAll('.checkbox')

    checkboxes.at(checkboxIndex).trigger('click')

    await editUserModal.find('button').trigger('click')

    return editUserModal
  }

  changeEmail(newEmail, options) {
    return this.changeUserEditField(newEmail, 1, options)
  }

  toggleIsStaff() {
    return this.changeUserCheckbox(1)
  }

  toggleIsActive() {
    return this.changeUserCheckbox(0)
  }

  clickNextPage() {
    return this.c.find('.iconoir-nav-arrow-right').trigger('click')
  }

  clickPrevPage() {
    return this.c.find('.iconoir-nav-arrow-left').trigger('click')
  }

  async typeIntoSearchBox(searchText) {
    const searchBox = this.c.findComponent(CrudTableSearch)
    const searchInput = searchBox.find('input')
    searchInput.element.value = searchText
    await searchInput.trigger('input')
    await searchInput.trigger('keyup')
  }

  clickUsernameHeader() {
    return this.clickHeaderAt(0)
  }

  clickFullnameHeader() {
    return this.clickHeaderAt(1)
  }

  clickHeaderAt(index) {
    return this.c
      .findAll('.data-table__table-cell-head-link')
      .at(index)
      .trigger('click')
  }

  async clickConfirmDeleteUserInModal() {
    await this.c
      .findComponent(DeleteUserModal)
      .find('.button--danger')
      .trigger('click')
  }
}
