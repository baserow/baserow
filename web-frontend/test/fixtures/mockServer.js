import { createApplication } from '@baserow/test/fixtures/applications'
import { createWorkspace } from '@baserow/test/fixtures/workspaces'
import {
  createGridView,
  createPublicGridView,
} from '@baserow/test/fixtures/view'
import { createFields } from '@baserow/test/fixtures/fields'
import {
  createPublicGridViewRows,
  createGridRows,
  deleteGridRow,
} from '@baserow/test/fixtures/grid'
import {
  createGalleryRows,
  createGalleryView,
} from '@baserow/test/fixtures/gallery'
import {
  expectUserDeleted,
  expectUserUpdated,
  expectUserUpdatedRespondsWithError,
  createUsersForAdmin,
  aUser,
} from '@baserow/test/fixtures/user'

/**
 * MockServer is responsible for being the single place where we mock out calls to the
 * baserow server API in tests. This way when an API change is made we should only
 * need to make one change in this class to reflect the change in the tests.
 */
export class MockServer {
  constructor(mock, store) {
    this.mock = mock
    this.store = store
  }

  loadPermissions(workspace, result = {}) {
    this.mock
      .onGet(`/workspaces/${workspace.id}/permissions/`)
      .reply(200, result)
  }

  async createAppAndWorkspace(table) {
    const workspace = createWorkspace(this.mock, {})
    this.loadPermissions(workspace)
    const application = createApplication(this.mock, {
      workspaceId: workspace.id,
      tables: [table],
    })
    table.database_id = application.id
    await this.store.dispatch('workspace/fetchAll')
    await this.store.dispatch('application/fetchAll')
    return { application, workspace }
  }

  async createAppAndWorkspaceWithMultipleTables(tables) {
    const workspace = createWorkspace(this.mock, {})
    this.loadPermissions(workspace)
    const application = createApplication(this.mock, {
      workspaceId: workspace.id,
      tables,
    })
    await this.store.dispatch('workspace/fetchAll')
    await this.store.dispatch('application/fetchAll')
    return { application, workspace }
  }

  createTable(id = 1, name = 'Test Table 1') {
    return { id, name, _: { disabled: false, selected: true } }
  }

  createGridView(
    application,
    table,
    { filters = [], sortings = [], groupBys = [], decorations = [], ...rest }
  ) {
    return createGridView(this.mock, application, table, {
      filters,
      sortings,
      groupBys,
      decorations,
      ...rest,
    })
  }

  createPublicGridView(viewSlug, { name, fields = [], sortings = [] }) {
    return createPublicGridView(this.mock, viewSlug, { name, fields, sortings })
  }

  createPublicGridViewRows(viewSlug, fields, rows) {
    return createPublicGridViewRows(this.mock, viewSlug, fields, rows)
  }

  createGalleryView(
    application,
    table,
    { filters = [], sortings = [], decorations = [], ...rest }
  ) {
    return createGalleryView(this.mock, application, table, {
      filters,
      sortings,
      decorations,
      ...rest,
    })
  }

  createFields(application, table, fields) {
    return createFields(this.mock, application, table, fields)
  }

  createGridRows(gridView, fields, rows) {
    return createGridRows(this.mock, gridView, fields, rows)
  }

  deleteGridRow(tableId, rowId, responseCode) {
    return deleteGridRow(this.mock, tableId, rowId, responseCode)
  }

  createGalleryRows(gridView, fields, rows) {
    return createGalleryRows(this.mock, gridView, fields, rows)
  }

  nextSearchForTermWillReturn(searchTerm, gridView, results) {
    this.mock
      .onGet(`/database/views/grid/${gridView.id}/`, {
        params: {
          asymmetricMatch(actual) {
            return (
              actual.get('count') === 'true' &&
              actual.get('search') === searchTerm
            )
          },
        },
      })
      .reply(200, {
        count: results.length,
      })

    this.mock
      .onGet(`/database/views/grid/${gridView.id}/`, {
        params: {
          asymmetricMatch(actual) {
            return (
              actual.get('limit') === '120' &&
              actual.get('offset') === '0' &&
              actual.get('search') === searchTerm &&
              actual.get('include') === 'row_metadata'
            )
          },
        },
      })
      .reply(200, {
        count: results.length,
        next: null,
        previous: null,
        results,
      })
  }

  creatingRowsInTableReturns(table, result) {
    this.mock
      .onPost(`/database/rows/table/${table.id}/batch/`)
      .reply(200, result)
  }

  updateViewFilter(filterId, newValue) {
    this.mock
      .onPatch(`/database/views/filter/${filterId}/`, { value: newValue })
      .reply(200)
  }

  updateFieldOptions(viewId, values) {
    this.mock
      .onPatch(`/database/views/${viewId}/field-options/`, {
        field_options: values,
      })
      .replyOnce(200)
  }

  // Grid view aggregation data mocks
  getFieldAggregationData(viewId, fieldId, rawType, result, error = false) {
    const mock = this.mock.onGet(
      `/database/views/grid/${viewId}/aggregation/${fieldId}/`,
      {
        params: {
          asymmetricMatch(actual) {
            return actual.get('type') === rawType
          },
        },
      }
    )
    if (error) {
      mock.replyOnce(500)
    } else {
      mock.replyOnce(200, result)
    }
  }

  getAllFieldAggregationData(viewId, result, error = false) {
    const mock = this.mock.onGet(`/database/views/grid/${viewId}/aggregations/`)
    if (error) {
      mock.replyOnce(500)
    } else {
      mock.replyOnce(200, result)
    }
  }

  createDecoration(view, values, result) {
    this.mock
      .onPost(`/database/views/${view.id}/decorations/`, values)
      .replyOnce(200, result)
  }

  updateDecoration(decoration, values, result) {
    this.mock
      .onPatch(`/database/views/decoration/${decoration.id}/`, values)
      .replyOnce(200, result)
  }

  deleteDecoration(decoration) {
    this.mock
      .onDelete(`/database/views/decoration/${decoration.id}/`)
      .replyOnce(200)
  }

  resetMockEndpoints() {
    this.mock.reset()
  }

  expectUserDeleted(userId) {
    expectUserDeleted(this.mock, userId)
  }

  expectUserUpdated(user, changes) {
    expectUserUpdated(this.mock, user, changes)
  }

  expectUserUpdatedRespondsWithError(user, error) {
    expectUserUpdatedRespondsWithError(this.mock, user, error)
  }

  thereAreUsers(users, page, options = {}) {
    createUsersForAdmin(this.mock, users, page, options)
  }

  aUser(user = {}) {
    return aUser(user)
  }
}
