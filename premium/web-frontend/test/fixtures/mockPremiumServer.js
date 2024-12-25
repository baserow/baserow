import { thereAreComments } from './comments'
import { createKanbanView, thereAreRowsInKanbanView } from './kanban'
import { createCalendarView, thereAreRowsInCalendarView } from './calendar'
import { MockServer } from '@baserow/test/fixtures/mockServer'

export default class MockPremiumServer extends MockServer {
  createKanbanView(
    application,
    table,
    {
      filters = [],
      sortings = [],
      groupBys = [],
      decorations = [],
      singleSelectFieldId = -1,
      ...rest
    }
  ) {
    return createKanbanView(this.mock, application, table, {
      filters,
      sortings,
      groupBys,
      decorations,
      singleSelectFieldId,
      ...rest,
    })
  }

  createCalendarView(
    application,
    table,
    {
      filters = [],
      sortings = [],
      groupBys = [],
      decorations = [],
      singleSelectFieldId = -1,
      ...rest
    }
  ) {
    return createCalendarView(this.mock, application, table, {
      filters,
      sortings,
      groupBys,
      decorations,
      singleSelectFieldId,
      ...rest,
    })
  }

  thereAreRowsInKanbanView(fieldOptions, rows) {
    thereAreRowsInKanbanView(this.mock, fieldOptions, rows)
  }

  thereAreRowsInCalendarView(fieldOptions, rows) {
    thereAreRowsInCalendarView(this.mock, fieldOptions, rows)
  }

  thereAreComments(comments, tableId, rowId) {
    thereAreComments(this.mock, comments, tableId, rowId)
  }

  expectPremiumViewUpdate(viewId, expectedContents) {
    this.mock
      .onPatch(`/database/view/${viewId}/premium`, expectedContents)
      .reply(200, expectedContents)
  }

  expectCalendarViewUpdate(viewId, expectedContents) {
    this.mock
      .onPatch(`/database/views/${viewId}/`, { ical_public: true })
      .reply((config) => {
        return [200, expectedContents]
      })
  }

  expectCalendarRefreshShareURLUpdate(viewId, expectedContents) {
    this.mock
      .onPost(`/database/views/calendar/${viewId}/ical_slug_rotate/`)
      .reply((config) => {
        return [200, expectedContents]
      })
  }
}
