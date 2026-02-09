import calendarStore from '@baserow_premium/store/view/calendar'
import { TestApp } from '@baserow/test/helpers/testApp'
import moment from '@baserow/modules/core/moment'

const fields = [
  {
    id: 1,
    table_id: 464,
    name: 'Name',
    order: 0,
    type: 'text',
    primary: true,
    read_only: false,
    text_default: '',
    _: {
      type: {
        type: 'text',
        iconClass: 'font',
        name: 'Single line text',
        isReadOnly: false,
        canImport: true,
      },
      loading: false,
    },
  },
  {
    id: 2,
    table_id: 464,
    name: 'Date without time',
    order: 1,
    type: 'date',
    primary: false,
    read_only: false,
    date_format: 'ISO',
    date_include_time: false,
    date_time_format: '24',
    date_show_tzinfo: true,
    date_force_timezone: null,
    _: {
      type: {
        type: 'date',
        iconClass: 'calendar-alt',
        name: 'Date',
        isReadOnly: false,
        canImport: true,
      },
      loading: false,
    },
  },
  {
    id: 3,
    table_id: 464,
    name: 'Date with time',
    order: 2,
    type: 'date',
    primary: false,
    read_only: false,
    date_format: 'ISO',
    date_include_time: true,
    date_time_format: '24',
    date_show_tzinfo: true,
    date_force_timezone: null,
    _: {
      type: {
        type: 'date',
        iconClass: 'calendar-alt',
        name: 'Date',
        isReadOnly: false,
        canImport: true,
      },
      loading: false,
    },
  },
  {
    id: 4,
    table_id: 464,
    name: 'Date with time (Kamchatka)',
    order: 3,
    type: 'date',
    primary: false,
    read_only: false,
    date_format: 'ISO',
    date_include_time: true,
    date_time_format: '24',
    date_show_tzinfo: true,
    date_force_timezone: 'Asia/Kamchatka',
    _: {
      type: {
        type: 'date',
        iconClass: 'calendar-alt',
        name: 'Date',
        isReadOnly: false,
        canImport: true,
      },
      loading: false,
    },
  },
  {
    id: 5,
    table_id: 464,
    name: 'Date without time (Kamchatka)',
    order: 1,
    type: 'date',
    primary: false,
    read_only: false,
    date_format: 'ISO',
    date_include_time: false,
    date_time_format: '24',
    date_show_tzinfo: true,
    date_force_timezone: 'Asia/Kamchatka',
    _: {
      type: {
        type: 'date',
        iconClass: 'calendar-alt',
        name: 'Date',
        isReadOnly: false,
        canImport: true,
      },
      loading: false,
    },
  },
]

describe('Calendar view store', () => {
  let testApp = null
  let store = null
  const view = {
    filters: [],
    filters_disabled: true,
  }

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: {
        calendar: calendarStore,
      },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  describe('getters', () => {
    beforeEach(() => {
      const dateStacks = {}
      dateStacks['2023-01-01'] = {
        count: 100,
        results: [
          { id: 10, order: '10.00', field_2: '2023-01-01T00:00:00Z' },
          { id: 11, order: '11.00', field_2: '2023-01-01T00:00:00Z' },
        ],
      }
      dateStacks['2023-01-02'] = {
        count: 2,
        results: [
          { id: 20, order: '20.00', field_2: '2023-01-02T00:00:00Z' },
          { id: 21, order: '21.00', field_2: '2023-01-02T00:00:00Z' },
        ],
      }

      // set up initial store state
      const state = Object.assign(calendarStore.state(), {
        lastCalendarId: 321,
        dateFieldId: 2,
        dateStacks,
        bufferRequestSize: 10,
        selectedDate: moment.tz(
          {
            year: 2022,
            month: 10,
            day: 17,
            hour: 0,
            minute: 0,
            second: 0,
            millisecond: 0,
          },
          'utc'
        ),
        fieldOptions: {
          1: {
            hidden: false,
            order: 32767,
          },
          2: {
            hidden: false,
            order: 32767,
          },
          3: {
            hidden: false,
            order: 32767,
          },
          4: {
            hidden: true,
            order: 32767,
          },
          5: {
            hidden: true,
            order: 32767,
          },
        },
      })

      store.replaceState({ ...store.state, calendar: state })
    })

    test('getLastCalendarId', () => {
      const result = store.getters['calendar/getLastCalendarId']
      expect(result).toBe(321)
    })

    test('getDateFieldIdIfNotTrashed', () => {
      const result =
        store.getters['calendar/getDateFieldIdIfNotTrashed'](fields)
      expect(result).toBe(2)
    })

    test('getAllFieldOptions', () => {
      const result = store.getters['calendar/getAllFieldOptions']
      expect(Object.keys(result).length).toBe(5)
      expect(result['4'].hidden).toBe(true)
    })

    test('getDateStack', () => {
      const result = store.getters['calendar/getDateStack']('2023-01-02')
      expect(result.results[0].id).toBe(20)
      expect(result.results[1].id).toBe(21)
    })

    test('getBufferRequestSize', () => {
      const result = store.getters['calendar/getBufferRequestSize']
      expect(result).toBe(10)
    })

    test('getSelectedDate', () => {
      const result = store.getters['calendar/getSelectedDate'](fields)
      expect(result.year()).toBe(2022)
      expect(result.month()).toBe(10)
      expect(result.date()).toBe(17)
    })

    test('getAllRows', () => {
      const allRows = store.getters['calendar/getAllRows']
      expect(allRows.length).toBe(4)
      expect(allRows[0].id).toBe(10)
      expect(allRows[1].id).toBe(11)
      expect(allRows[2].id).toBe(20)
      expect(allRows[3].id).toBe(21)
    })

    test('findStackIdAndIndex', () => {
      const stackAndIndex = store.getters['calendar/findStackIdAndIndex'](21)
      expect(stackAndIndex).toStrictEqual([
        '2023-01-02',
        1,
        { field_2: '2023-01-02T00:00:00Z', id: 21, order: '21.00' },
      ])
    })
  })

  describe('actions', () => {
    describe('createdNewRow', () => {
      describe('date field in UTC', () => {
        test('new rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_2: '2023-01-01T00:00:00Z' },
              { id: 11, order: '11.00', field_2: '2023-01-01T00:00:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 2,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 1,
              order: '1.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 3,
              order: '3.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            fields,
          })

          // if adding last row in a stack, it won't be added to the store
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 12,
              order: '12.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(103)
          expect(resultStack.results.length).toBe(4)
          expect(resultStack.results[0].id).toBe(1)
          expect(resultStack.results[1].id).toBe(3)
          expect(resultStack.results[2].id).toBe(10)
          expect(resultStack.results[3].id).toBe(11)
        })

        test('new rows added across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_2: '2023-01-01T00:00:00Z' },
              { id: 11, order: '11.00', field_2: '2023-01-01T00:00:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 0,
            results: [],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 2,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 6,
              order: '6.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 1,
              order: '1.00',
              field_2: '2023-01-02T00:00:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 3,
              order: '3.00',
              field_2: '2023-01-02T00:00:00Z',
            },
            fields,
          })

          // if date stack doesn't exist, it won't be created
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 4,
              order: '4.00',
              field_2: '2023-01-03T00:00:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(101)
          expect(resultStack1st.results.length).toBe(3)
          expect(resultStack1st.results[0].id).toBe(6)
          expect(resultStack1st.results[1].id).toBe(10)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(2)
          expect(resultStack2nd.results.length).toBe(2)
          expect(resultStack2nd.results[0].id).toBe(1)
          expect(resultStack2nd.results[1].id).toBe(3)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)
        })
      })

      describe('date field in a set timezone', () => {
        test('new rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_5: '2023-01-01T12:00:00Z' },
              { id: 11, order: '11.00', field_5: '2023-01-01T12:00:00Z' },
            ],
          }
          dateStacks['2022-12-31'] = {
            count: 0,
            results: [],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 5,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 1,
              order: '1.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 3,
              order: '3.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            fields,
          })

          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 12,
              order: '12.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(100)
          expect(resultStack.results.length).toBe(2)
          expect(resultStack.results[0].id).toBe(10)
          expect(resultStack.results[1].id).toBe(11)
          const resultStackDayBefore =
            store.state.calendar.dateStacks['2022-12-31']
          expect(resultStackDayBefore.count).toBe(3)
          expect(resultStackDayBefore.results.length).toBe(3)
          expect(resultStackDayBefore.results[0].id).toBe(1)
          expect(resultStackDayBefore.results[1].id).toBe(3)
          expect(resultStackDayBefore.results[2].id).toBe(12)
        })

        test('new rows added across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_5: '2023-01-01T12:00:00Z' },
              { id: 11, order: '11.00', field_5: '2023-01-01T12:00:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 0,
            results: [],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 5,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 6,
              order: '6.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 1,
              order: '1.00',
              field_5: '2023-01-01T12:00:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 3,
              order: '3.00',
              field_5: '2023-01-01T12:00:00Z',
            },
            fields,
          })

          // if date stack doesn't exist, it won't be created
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 4,
              order: '4.00',
              field_5: '2023-01-02T12:00:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(102)
          expect(resultStack1st.results.length).toBe(4)
          expect(resultStack1st.results[0].id).toBe(1)
          expect(resultStack1st.results[1].id).toBe(3)
          expect(resultStack1st.results[2].id).toBe(10)
          expect(resultStack1st.results[3].id).toBe(11)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(1)
          expect(resultStack2nd.results.length).toBe(1)
          expect(resultStack2nd.results[0].id).toBe(4)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)
        })
      })

      describe('date and time field in UTC', () => {
        test('new rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_3: '2023-01-01T00:30:00Z' },
              { id: 11, order: '11.00', field_3: '2023-01-01T23:30:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 3,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 1,
              order: '1.00',
              field_3: '2023-01-01T06:30:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 3,
              order: '3.00',
              field_3: '2023-01-01T00:10:00Z',
            },
            fields,
          })

          // if adding last row in a stack, it won't be added to the store
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 4,
              order: '4.00',
              field_3: '2023-01-01T23:59:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(103)
          expect(resultStack.results.length).toBe(4)
          expect(resultStack.results[0].id).toBe(3)
          expect(resultStack.results[1].id).toBe(10)
          expect(resultStack.results[2].id).toBe(1)
          expect(resultStack.results[3].id).toBe(11)
        })

        test('new rows added across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_3: '2023-01-01T00:30:00Z' },
              { id: 11, order: '11.00', field_3: '2023-01-01T23:30:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 0,
            results: [],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 3,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 6,
              order: '6.00',
              field_3: '2023-01-01T06:30:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 1,
              order: '1.00',
              field_3: '2023-01-02T06:30:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 3,
              order: '3.00',
              field_3: '2023-01-02T00:10:00Z',
            },
            fields,
          })

          // if date stack doesn't exist, it won't be created
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 4,
              order: '4.00',
              field_3: '2023-01-03T23:59:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(101)
          expect(resultStack1st.results.length).toBe(3)
          expect(resultStack1st.results[0].id).toBe(10)
          expect(resultStack1st.results[1].id).toBe(6)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(2)
          expect(resultStack2nd.results.length).toBe(2)
          expect(resultStack2nd.results[0].id).toBe(3)
          expect(resultStack2nd.results[1].id).toBe(1)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)
        })
      })

      describe('date and time field in set timezone', () => {
        test('new rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_4: '2023-01-01T09:30:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 4,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 11,
              order: '11.00',
              field_4: '2022-12-31T17:30:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 12,
              order: '12.00',
              field_4: '2022-12-31T17:29:00Z',
            },
            fields,
          })

          // if adding last row in a stack, it won't be added to the store
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 16,
              order: '16.00',
              field_4: '2022-01-01T10:00:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(102)
          expect(resultStack.results.length).toBe(3)
          expect(resultStack.results[0].id).toBe(12)
          expect(resultStack.results[1].id).toBe(11)
          expect(resultStack.results[2].id).toBe(10)
        })

        test('new rows added across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_4: '2023-01-01T11:50:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 0,
            results: [],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 4,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // add rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 6,
              order: '6.00',
              field_4: '2023-01-01T10:30:00Z',
            },
            fields,
          })
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 3,
              order: '3.00',
              field_4: '2023-01-02T00:10:00Z',
            },
            fields,
          })

          // if date stack doesn't exist, it won't be created
          await store.dispatch('calendar/createdNewRow', {
            view,
            values: {
              id: 4,
              order: '4.00',
              field_4: '2023-01-02T23:59:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(101)
          expect(resultStack1st.results[0].id).toBe(6)
          expect(resultStack1st.results[1].id).toBe(10)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(1)
          expect(resultStack2nd.results.length).toBe(1)
          expect(resultStack2nd.results[0].id).toBe(3)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)
        })
      })
    })

    describe('updatedExistingRow', () => {
      describe('date field in UTC', () => {
        test('updated rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_2: '2023-01-01T00:00:00Z' },
              { id: 11, order: '11.00', field_2: '2023-01-01T00:00:00Z' },
              { id: 22, order: '22.00', field_2: '2023-01-01T00:00:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 2,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 22,
              order: '22.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            values: {
              id: 22,
              order: '5.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            fields,
          })

          // updated rows to last position won't be in the store
          // anymore
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 11,
              order: '11.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            values: {
              id: 11,
              order: '23.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            fields,
          })

          // updating a row that doesn't exist in the stack yet
          // will add it
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 100,
              order: '1.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            values: {
              id: 100,
              order: '2.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(100)
          expect(resultStack.results.length).toBe(3)
          expect(resultStack.results[0].id).toBe(100)
          expect(resultStack.results[1].id).toBe(22)
          expect(resultStack.results[2].id).toBe(10)
        })

        test('moving rows across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_2: '2023-01-01T00:00:00Z' },
              { id: 11, order: '11.00', field_2: '2023-01-01T00:00:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 2,
            results: [
              { id: 20, order: '20.00', field_2: '2023-01-02T00:00:00Z' },
              { id: 21, order: '21.00', field_2: '2023-01-02T00:00:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 2,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 10,
              order: '10.00',
              field_2: '2023-01-01T00:00:00Z',
            },
            values: {
              id: 10,
              order: '10.00',
              field_2: '2023-01-02T00:00:00Z',
            },
            fields,
          })

          // if date stack doesn't exist, it won't be created
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 4,
              order: '4.00',
              field_2: '2023-01-03T00:00:00Z',
            },
            values: {
              id: 4,
              order: '4.00',
              field_2: '2023-01-03T00:00:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(99)
          expect(resultStack1st.results.length).toBe(1)
          expect(resultStack1st.results[0].id).toBe(11)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(3)
          expect(resultStack2nd.results.length).toBe(3)
          expect(resultStack2nd.results[0].id).toBe(10)
          expect(resultStack2nd.results[1].id).toBe(20)
          expect(resultStack2nd.results[2].id).toBe(21)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)
        })
      })

      describe('date field in a set timezone', () => {
        test('update rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_5: '2022-12-31T12:00:00Z' },
              { id: 11, order: '11.00', field_5: '2022-12-31T12:00:00Z' },
              { id: 22, order: '22.00', field_5: '2022-12-31T12:00:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 5,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 22,
              order: '22.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            values: {
              id: 22,
              order: '1.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            fields,
          })

          // updated rows to last position won't be in the store
          // anymore
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 11,
              order: '11.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            values: {
              id: 11,
              order: '23.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            fields,
          })

          // updating a row that doesn't exist in the stack
          // doesn't produce error
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 100,
              order: '100.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            values: {
              id: 100,
              order: '101.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(100)
          expect(resultStack.results.length).toBe(3)
          expect(resultStack.results[0].id).toBe(10)
          expect(resultStack.results[1].id).toBe(11)
        })

        test('moving rows across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_5: '2022-12-31T12:00:00Z' },
              { id: 11, order: '11.00', field_5: '2022-12-31T12:00:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 2,
            results: [
              { id: 20, order: '20.00', field_5: '2023-01-01T12:00:00Z' },
              { id: 21, order: '21.00', field_5: '2023-01-01T12:00:00Z' },
            ],
          }
          dateStacks['2023-01-04'] = {
            count: 0,
            results: [],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 5,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 10,
              order: '10.00',
              field_5: '2022-12-31T12:00:00Z',
            },
            values: {
              id: 10,
              order: '10.00',
              field_5: '2023-01-01T12:00:00Z',
            },
            fields,
          })

          // if the row didn't exist in any old stack,
          // it should still appear in a new one if that
          // one exists
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 400,
              order: '400.00',
              field_5: '2024-01-02T12:00:00Z',
            },
            values: {
              id: 400,
              order: '400.00',
              field_5: '2023-01-03T12:00:00Z',
            },
            fields,
          })

          // if the target date stack doesn't exist, it won't be created
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 4,
              order: '4.00',
              field_5: '2023-01-02T12:00:00Z',
            },
            values: {
              id: 4,
              order: '4.00',
              field_5: '2023-01-02T12:00:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(100)
          expect(resultStack1st.results.length).toBe(2)
          expect(resultStack1st.results[0].id).toBe(10)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(3)
          expect(resultStack2nd.results.length).toBe(3)
          expect(resultStack2nd.results[0].id).toBe(20)
          expect(resultStack2nd.results[1].id).toBe(21)
          expect(resultStack2nd.results[2].id).toBe(4)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)

          const resultStack4th = store.state.calendar.dateStacks['2023-01-04']
          expect(resultStack4th.count).toBe(0)
        })
      })

      describe('date and time field in UTC', () => {
        test('updated rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_3: '2023-01-01T00:30:00Z' },
              { id: 11, order: '11.00', field_3: '2023-01-01T23:30:00Z' },
              { id: 22, order: '22.00', field_3: '2023-01-01T23:50:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 3,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 22,
              order: '22.00',
              field_3: '2023-01-01T23:50:00Z',
            },
            values: {
              id: 22,
              order: '22.00',
              field_3: '2023-01-01T06:30:00Z',
            },
            fields,
          })

          // updated rows to last position won't be in the store
          // anymore
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 11,
              order: '11.00',
              field_3: '2023-01-01T23:30:00Z',
            },
            values: {
              id: 11,
              order: '23.00',
              field_3: '2023-01-01T23:55:00Z',
            },
            fields,
          })

          // updating a row that doesn't exist in the stack yet
          // will add it
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 100,
              order: '100.00',
              field_3: '2023-01-01T00:00:00Z',
            },
            values: {
              id: 100,
              order: '101.00',
              field_3: '2023-01-01T00:00:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(100)
          expect(resultStack.results.length).toBe(3)
          expect(resultStack.results[0].id).toBe(100)
          expect(resultStack.results[1].id).toBe(10)
          expect(resultStack.results[2].id).toBe(22)
        })

        test('moving rows across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_3: '2023-01-01T00:30:00Z' },
              { id: 11, order: '11.00', field_3: '2023-01-01T23:30:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 2,
            results: [
              { id: 20, order: '20.00', field_3: '2023-01-02T10:00:00Z' },
              { id: 21, order: '21.00', field_3: '2023-01-02T15:00:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 3,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 10,
              order: '10.00',
              field_3: '2023-01-01T00:30:00Z',
            },
            values: {
              id: 10,
              order: '10.00',
              field_3: '2023-01-02T00:30:00Z',
            },
            fields,
          })

          // if date stack doesn't exist, it won't be created
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 21,
              order: '21.00',
              field_3: '2023-01-02T15:00:00Z',
            },
            values: {
              id: 21,
              order: '21.00',
              field_3: '2023-01-03T00:00:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(99)
          expect(resultStack1st.results.length).toBe(1)
          expect(resultStack1st.results[0].id).toBe(11)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(2)
          expect(resultStack2nd.results.length).toBe(2)
          expect(resultStack2nd.results[0].id).toBe(10)
          expect(resultStack2nd.results[1].id).toBe(20)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)
        })
      })

      describe('date and time field in set timezone', () => {
        test('updated rows sorted within the same date', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_4: '2022-12-31T12:30:00Z' },
              { id: 11, order: '11.00', field_4: '2023-01-01T11:30:00Z' },
              { id: 22, order: '22.00', field_4: '2023-01-01T11:50:00Z' },
            ],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 4,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows that should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 22,
              order: '22.00',
              field_4: '2023-01-01T11:50:00Z',
            },
            values: {
              id: 22,
              order: '22.00',
              field_4: '2022-12-31T18:30:00Z',
            },
            fields,
          })

          // updated rows to last position won't be in the store
          // anymore
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 11,
              order: '11.00',
              field_4: '2023-01-01T11:30:00Z',
            },
            values: {
              id: 11,
              order: '23.00',
              field_4: '2023-01-01T11:55:00Z',
            },
            fields,
          })

          // updating a row that doesn't exist in the stack yet
          // will add it
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 100,
              order: '100.00',
              field_4: '2022-12-31T12:00:00Z',
            },
            values: {
              id: 100,
              order: '101.00',
              field_4: '2022-12-31T12:00:00Z',
            },
            fields,
          })

          const resultStack = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack.count).toBe(100)
          expect(resultStack.results.length).toBe(3)
          expect(resultStack.results[0].id).toBe(100)
          expect(resultStack.results[1].id).toBe(10)
          expect(resultStack.results[2].id).toBe(22)
        })

        test('moving rows across dates', async () => {
          const dateStacks = {}
          dateStacks['2023-01-01'] = {
            count: 100,
            results: [
              { id: 10, order: '10.00', field_5: '2022-12-31T12:30:00Z' },
              { id: 11, order: '11.00', field_5: '2023-01-01T11:30:00Z' },
            ],
          }
          dateStacks['2023-01-02'] = {
            count: 2,
            results: [
              { id: 20, order: '20.00', field_5: '2023-01-01T23:00:00Z' },
              { id: 21, order: '21.00', field_5: '2023-01-02T03:00:00Z' },
            ],
          }
          dateStacks['2023-01-04'] = {
            count: 0,
            results: [],
          }

          // set up initial store state
          const state = Object.assign(calendarStore.state(), {
            dateFieldId: 5,
            dateStacks,
          })
          store.replaceState({ ...store.state, calendar: state })

          // updated rows should get assigned to correct
          // date bucket in a sorted order
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 10,
              order: '10.00',
              field_5: '2022-12-31T12:30:00Z',
            },
            values: {
              id: 10,
              order: '10.00',
              field_5: '2023-01-01T12:30:00Z',
            },
            fields,
          })

          // if date stack doesn't exist, it won't be created
          await store.dispatch('calendar/updatedExistingRow', {
            view,
            row: {
              id: 21,
              order: '21.00',
              field_5: '2023-01-02T03:00:00Z',
            },
            values: {
              id: 21,
              order: '21.00',
              field_5: '2023-01-03T03:00:00Z',
            },
            fields,
          })

          const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
          expect(resultStack1st.count).toBe(100)
          expect(resultStack1st.results.length).toBe(2)
          expect(resultStack1st.results[0].id).toBe(10)

          const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
          expect(resultStack2nd.count).toBe(1)
          expect(resultStack2nd.results.length).toBe(1)
          expect(resultStack2nd.results[0].id).toBe(20)

          const resultStack3rd = store.state.calendar.dateStacks['2023-01-03']
          expect(resultStack3rd).toBe(undefined)
        })
      })
    })

    describe('deletedExistingRow', () => {
      test('date and time in a set timezone', async () => {
        const dateStacks = {}
        dateStacks['2023-01-01'] = {
          count: 100,
          results: [
            { id: 10, order: '10.00', field_5: '2022-12-31T12:30:00Z' },
            { id: 11, order: '11.00', field_5: '2023-01-01T11:30:00Z' },
          ],
        }
        dateStacks['2023-01-02'] = {
          count: 5,
          results: [],
        }

        // set up initial store state
        const state = Object.assign(calendarStore.state(), {
          dateFieldId: 5,
          dateStacks,
        })
        store.replaceState({ ...store.state, calendar: state })

        // deleting existing row
        await store.dispatch('calendar/deletedExistingRow', {
          view,
          row: {
            id: 10,
            order: '10.00',
            field_5: '2022-12-31T12:30:00Z',
          },
          fields,
        })

        // deleting non-existing row in existing stack
        await store.dispatch('calendar/deletedExistingRow', {
          view,
          row: {
            id: 13,
            order: '13.00',
            field_5: '2023-01-02T11:30:00Z',
          },
          fields,
        })

        // deleting non-existing row in not-existing stack
        await store.dispatch('calendar/deletedExistingRow', {
          view,
          row: {
            id: 13,
            order: '13.00',
            field_5: '2023-01-05T11:30:00Z',
          },
          fields,
        })

        const resultStack1st = store.state.calendar.dateStacks['2023-01-01']
        expect(resultStack1st.count).toBe(99)
        expect(resultStack1st.results.length).toBe(1)
        expect(resultStack1st.results[0].id).toBe(11)

        const resultStack2nd = store.state.calendar.dateStacks['2023-01-02']
        expect(resultStack2nd.count).toBe(4)
      })
    })
  })
})
