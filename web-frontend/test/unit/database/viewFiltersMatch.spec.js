import { TestApp } from '@baserow/test/helpers/testApp'
import moment from '@baserow/modules/core/moment'
import {
  BooleanViewFilterType,
  DateAfterDaysAgoViewFilterType,
  DateAfterOrEqualViewFilterType,
  DateAfterTodayViewFilterType,
  DateAfterViewFilterType,
  DateBeforeOrEqualViewFilterType,
  DateBeforeTodayViewFilterType,
  DateBeforeViewFilterType,
  DateEqualsCurrentMonthViewFilterType,
  DateEqualsCurrentWeekViewFilterType,
  DateEqualsCurrentYearViewFilterType,
  DateEqualsDaysAgoViewFilterType,
  DateEqualsTodayViewFilterType,
  DateEqualsYearsAgoViewFilterType,
  DateEqualViewFilterType,
  DateIsAfterMultiStepViewFilterType,
  DateIsBeforeMultiStepViewFilterType,
  DateIsEqualMultiStepViewFilterType,
  DateIsNotEqualMultiStepViewFilterType,
  DateIsOnOrAfterMultiStepViewFilterType,
  DateIsOnOrBeforeMultiStepViewFilterType,
  DateIsWithinMultiStepViewFilterType,
  DateNotEqualViewFilterType,
  DateWithinDaysViewFilterType,
  DateWithinMonthsViewFilterType,
  DateWithinWeeksViewFilterType,
  EmptyViewFilterType,
  EqualViewFilterType,
  FilesLowerThanViewFilterType,
  HasFileTypeViewFilterType,
  HigherThanOrEqualViewFilterType,
  HigherThanViewFilterType,
  IsEvenAndWholeViewFilterType,
  LengthIsLowerThanViewFilterType,
  LinkRowContainsFilterType,
  LinkRowNotContainsFilterType,
  LowerThanOrEqualViewFilterType,
  LowerThanViewFilterType,
  MultipleSelectHasFilterType,
  MultipleSelectHasNotFilterType,
  NotEmptyViewFilterType,
  SingleSelectIsAnyOfViewFilterType,
  SingleSelectIsNoneOfViewFilterType,
} from '@baserow/modules/database/viewFilters'
import {
  DurationFieldType,
  FormulaFieldType,
  NumberFieldType,
  SingleSelectFieldType,
  MultipleSelectFieldType,
  MultipleCollaboratorsFieldType,
} from '@baserow/modules/database/fieldTypes'

export const dateBeforeCases = [
  {
    rowValue: '2021-08-10T21:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-10T22:59:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10T22:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-10T23:01:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-10T23:59:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T00:01:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
]

export const dateAfterCases = [
  {
    rowValue: '2021-08-11T22:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-12',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11T23:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T21:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11T22:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-12T00:01:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-12',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T23:59:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
]

export const dateBeforeOrEqualCases = [
  {
    rowValue: '2021-08-10T21:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10T22:59:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10T22:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-10',
    expected: false,
  },
  {
    rowValue: '2021-08-10T23:01:37.940086Z',
    filterValue: 'Europe/London?2021-08-10',
    expected: false,
  },
  {
    rowValue: '2021-08-10T23:59:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T00:01:37.940086Z',
    filterValue: 'UTC?2021-08-10',
    expected: false,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'UTC?2021-08-10',
    expected: false,
  },
]

export const dateAfterOrEqualCases = [
  {
    rowValue: '2021-08-11T22:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-12',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10',
    filterValue: 'Europe/Berlin?2021-08-09',
    expected: true,
  },
  {
    rowValue: '2021-08-11T23:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T21:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-12',
    expected: false,
  },
  {
    rowValue: '2021-08-10T22:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-12',
    expected: false,
  },
  {
    rowValue: '2021-08-12T00:01:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-12',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T23:59:37.940086Z',
    filterValue: 'UTC?2021-08-12',
    expected: false,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'UTC?2021-08-12',
    expected: false,
  },
]

export const dateEqualCases = [
  {
    rowValue: '2021-08-11T21:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T22:59:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10T22:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10T23:01:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10T21:59:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-10T22:59:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11T23:59:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'CET?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T00:01:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-12T00:01:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-12',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
]

export const dateNotEqualCases = [
  {
    rowValue: '2021-08-11T22:30:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T21:30:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-12',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11T23:30:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-10T22:01:37.940086Z',
    filterValue: 'Europe/Berlin?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-10T23:01:37.940086Z',
    filterValue: 'Europe/London?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11T23:59:37.940086Z',
    filterValue: 'UTC?2021-08-12',
    expected: true,
  },
  {
    rowValue: '2021-08-13T00:01:37.940086Z',
    filterValue: 'UTC?2021-08-12',
    expected: true,
  },
  {
    rowValue: '2021-08-10',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-12',
    filterValue: 'UTC?2021-08-11',
    expected: true,
  },
  {
    rowValue: '2021-08-11T22:59:37.940086Z',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
  {
    rowValue: '2021-08-11',
    filterValue: 'UTC?2021-08-11',
    expected: false,
  },
]

export const dateToday = [
  {
    rowValue: moment().utc().format(),
    filterValue: 'Europe/Berlin',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin',
    expected: false,
  },
]

export const dateBeforeToday = [
  {
    rowValue: moment().utc().format(),
    filterValue: 'Europe/Berlin',
    expected: false,
  },
  {
    rowValue: moment().subtract(1, 'day').utc().format(),
    filterValue: 'Europe/Berlin',
    expected: true,
  },
  {
    rowValue: moment().add(1, 'day').utc().format(),
    filterValue: 'Europe/Berlin',
    expected: false,
  },
]

export const dateAfterToday = [
  {
    rowValue: moment().utc().format(),
    filterValue: 'Europe/Berlin',
    expected: false,
  },
  {
    rowValue: moment().subtract(1, 'day').utc().format(),
    filterValue: 'Europe/Berlin',
    expected: false,
  },
  {
    rowValue: moment().add(1, 'day').utc().format(),
    filterValue: 'Europe/Berlin',
    expected: true,
  },
]

export const dateInThisWeek = [
  {
    rowValue: '2022-05-29',
    filterValue: 'Europe/Berlin',
    expected: false,
  },
  {
    rowValue: '2022-05-29T12:00:00.000000Z',
    filterValue: 'Europe/Berlin',
    expected: false,
  },
  {
    rowValue: '2022-05-30',
    filterValue: 'Europe/Berlin',
    expected: true,
  },
  {
    rowValue: '2022-05-30T12:00:00.000000Z',
    filterValue: 'Europe/Berlin',
    expected: true,
  },
  {
    rowValue: '2022-06-05T12:00:00.000000Z',
    filterValue: 'Europe/Berlin',
    expected: true,
  },
  {
    rowValue: '2022-06-06T12:00:00.000000Z',
    filterValue: 'Europe/Berlin',
    expected: false,
  },
]

export const dateInThisMonth = [
  {
    rowValue: '2022-05-01T12:00:00.000000Z',
    filterValue: 'Europe/Berlin?',
    expected: false,
  },
  {
    rowValue: '2022-05-31T21:59:00.000000Z',
    filterValue: 'Europe/Berlin?',
    expected: false,
  },
  {
    rowValue: '2022-06-01T12:00:00.000000Z',
    filterValue: 'Europe/Berlin?',
    expected: true,
  },
  {
    rowValue: '2022-06-30T21:59:00.000000Z',
    filterValue: 'Europe/Berlin?',
    expected: true,
  },
  {
    rowValue: '2022-07-01T00:01:00.000000Z',
    filterValue: 'Europe/Berlin?',
    expected: false,
  },
  {
    rowValue: '2022-05-31T23:59:00.000000Z',
    filterValue: 'Europe/London?',
    expected: true,
  },
]

export const dateInThisYear = [
  {
    rowValue: '2021-06-01T12:00:00.000000Z',
    filterValue: 'Europe/Berlin?',
    expected: false,
  },
  {
    rowValue: '2022-06-01T12:00:00.000000Z',
    filterValue: 'Europe/Berlin?',
    expected: true,
  },
]
export const dateWithinDaysAgo = [
  {
    rowValue: moment().tz('Europe/Berlin').subtract(1, 'days').format(),
    filterValue: 'Europe/Berlin?1',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin?2',
    expected: false,
  },
  {
    rowValue: moment().utc().subtract(2, 'days').format(),
    filterValue: 'UTC?3',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: 'UTC?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().add(1, 'days').format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().add(1, 'days').format(),
    filterValue: '',
    expected: true,
  },
]

export const dateWithinDays = [
  {
    rowValue: moment().tz('Europe/Berlin').add(1, 'days').format(),
    filterValue: 'Europe/Berlin?1',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin?2',
    expected: false,
  },
  {
    rowValue: moment().utc().add(2, 'days').format(),
    filterValue: 'UTC?3',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: 'UTC?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '',
    expected: true,
  },
]

export const dateWithinWeeks = [
  {
    rowValue: moment().tz('Europe/Berlin').add(5, 'days').format(),
    filterValue: 'Europe/Berlin?1',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin?2',
    expected: false,
  },
  {
    rowValue: moment().utc().add(20, 'days').format(),
    filterValue: 'UTC?3',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: 'UTC?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '?1',
    expected: false,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '',
    expected: true,
  },
]

export const dateWithinMonths = [
  {
    rowValue: moment().tz('Europe/Berlin').add(20, 'days').format(),
    filterValue: 'Europe/Berlin?1',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin?2',
    expected: false,
  },
  {
    rowValue: moment().utc().add(80, 'days').format(),
    filterValue: 'UTC?3',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: 'UTC?1',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '',
    expected: true,
  },
]

export const dateDaysAgo = [
  {
    rowValue: moment().utc().tz('Europe/Berlin').subtract(1, 'days').format(),
    filterValue: 'Europe/Berlin?1',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin?2',
    expected: false,
  },
  {
    rowValue: moment().utc().subtract(3, 'days').format(),
    filterValue: 'UTC?3',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: false,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: 'UTC?1',
    expected: false,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'days').format(),
    filterValue: '',
    expected: true,
  },
]

export const dateMonthsAgo = [
  {
    rowValue: moment().tz('Europe/Berlin').subtract(1, 'months').format(),
    filterValue: 'Europe/Berlin?1',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin?2',
    expected: false,
  },
  {
    rowValue: moment().utc().subtract(3, 'months').format(),
    filterValue: 'UTC?3',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: false,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: 'UTC?1',
    expected: false,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'months').format(),
    filterValue: '?1',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'months').format(),
    filterValue: '',
    expected: true,
  },
]

export const dateYearsAgo = [
  {
    rowValue: moment().tz('Europe/Berlin').subtract(1, 'years').format(),
    filterValue: 'Europe/Berlin?1',
    expected: true,
  },
  {
    rowValue: '1970-08-11T23:30:37.940086Z',
    filterValue: 'Europe/Berlin?2',
    expected: false,
  },
  {
    rowValue: moment().utc().subtract(3, 'years').format(),
    filterValue: 'UTC?3',
    expected: true,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?1',
    expected: false,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: 'UTC?1',
    expected: false,
  },
  {
    rowValue: moment().utc().format(),
    filterValue: '?0',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'years').format(),
    filterValue: 'UTC?1',
    expected: true,
  },
  {
    rowValue: moment().utc().subtract(1, 'years').format(),
    filterValue: '?1',
    expected: true,
  },
]

const multipleSelectValuesHas = [
  {
    rowValue: [
      { id: 155, value: 'A', color: 'green' },
      { id: 154, value: 'B', color: 'green' },
    ],
    filterValue: '154',
    expected: true,
  },
  {
    rowValue: [
      { id: 155, value: 'A', color: 'green' },
      { id: 154, value: 'B', color: 'green' },
    ],
    filterValue: '200,201',
    expected: false,
  },
  {
    rowValue: [
      { id: 155, value: 'A', color: 'green' },
      { id: 154, value: 'B', color: 'green' },
    ],
    filterValue: 'wrong_type',
    expected: false,
  },
]

const multipleSelectValuesHasNot = [
  {
    rowValue: [
      { id: 155, value: 'A', color: 'green' },
      { id: 154, value: 'B', color: 'green' },
    ],
    filterValue: '154,155',
    expected: false,
  },
  {
    rowValue: [
      { id: 155, value: 'A', color: 'green' },
      { id: 154, value: 'B', color: 'green' },
    ],
    filterValue: '200',
    expected: true,
  },
  {
    rowValue: [
      { id: 155, value: 'A', color: 'green' },
      { id: 154, value: 'B', color: 'green' },
    ],
    filterValue: 'wrong_type',
    expected: true,
  },
]

const lengthIsLowerThanCases = [
  {
    rowValue: 'bill',
    filterValue: 0,
    expected: true,
  },
  {
    rowValue: 'bill',
    filterValue: 1,
    expected: false,
  },
  {
    rowValue: 'bill',
    filterValue: 4,
    expected: false,
  },
  {
    rowValue: 'bill',
    filterValue: 5,
    expected: true,
  },
  {
    rowValue: 'bill',
    filterValue: 'a',
    expected: true,
  },
]

/**
 * SingleSelectIsAnyOfViewFilterType and SingleSelectIsNoneOfViewFilterType test values.
 *
 * In case of SingleSelectIsNoneOfViewFilterType we expect negation of .expected
 */
const singleSelectValuesInFilterCases = [
  {
    rowValue: { id: 1 },
    filterValue: '1,2',
    is_any_of: true,
    is_none_of: false,
  },
  {
    rowValue: { id: 2 },
    filterValue: '1,2',
    is_any_of: true,
    is_none_of: false,
  },
  {
    rowValue: { id: 3 },
    filterValue: '1,2',
    is_any_of: false,
    is_none_of: true,
  },
  {
    rowValue: { id: 4 },
    filterValue: '1,2',
    is_any_of: false,
    is_none_of: true,
  },
  {
    rowValue: { id: 5 },
    filterValue: '1',
    is_any_of: false,
    is_none_of: true,
  },
  {
    rowValue: { id: 5 },
    filterValue: '1, 5',
    is_any_of: true,
    is_none_of: false,
  },
  {
    rowValue: { id: 5 },
    filterValue: '',
    is_any_of: true,
    is_none_of: true,
  },
  {
    rowValue: null,
    filterValue: '',
    is_any_of: true,
    is_none_of: true,
  },
  {
    rowValue: { id: 1 },
    filterValue: '',
    is_any_of: true,
    is_none_of: true,
  },
  {
    rowValue: { id: 1 },
    filterValue: 'test,test2',
    is_any_of: false,
    is_none_of: true,
  },
  {
    rowValue: { id: 1 },
    filterValue: '1,test2',
    is_any_of: true,
    is_none_of: false,
  },
]

describe('(DEPRECATED) Date in this week, month and year tests', () => {
  let testApp = null
  let dateNowSpy

  beforeAll(() => {
    testApp = new TestApp()
    // Wed Jun 01 2022 00:00:00 UTC
    dateNowSpy = jest.spyOn(Date, 'now').mockImplementation(() => 1654041600000)
  })

  afterAll(() => {
    dateNowSpy.mockRestore()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test.each(dateInThisWeek)(
    '(DEPRECATED) DateInThisWeek with timezone.',
    (values) => {
      const result = new DateEqualsCurrentWeekViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, {
        date_include_time: true,
      })
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateInThisWeek)('DateInThisWeek with timezone.', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}??this_week`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateInThisWeek)(
    '(DEPRECATED) DateInThisWeek without timezone.',
    (values) => {
      const result = new DateEqualsCurrentWeekViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, {})
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateInThisWeek)('DateInThisWeek without timezone.', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}??this_week`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateInThisMonth)('(DEPRECATED) DateInThisMonth', (values) => {
    const result = new DateEqualsCurrentMonthViewFilterType({
      app: testApp,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateInThisMonth)('DateInThisMonth', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?this_month`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateInThisYear)('(DEPRECATED) DateInThisYear', (values) => {
    const result = new DateEqualsCurrentYearViewFilterType({
      app: testApp,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateInThisYear)('DateInThisYear', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?this_year`, {})
    expect(result).toBe(values.expected)
  })
})

const linkRowContainsCases = [
  {
    rowValue: [{ value: 'bill' }],
    filterValue: '',
    expected: true,
  },
  {
    rowValue: [{ value: 'bill' }],
    filterValue: 'bi',
    expected: true,
  },
  {
    rowValue: [{ value: 'some other name' }],
    filterValue: 'bill',
    expected: false,
  },
  {
    rowValue: [{ value: 'some other name' }, { value: 'bill' }],
    filterValue: 'bill',
    expected: true,
  },
  {
    rowValue: [{ value: 'BILL' }],
    filterValue: 'bill',
    expected: true,
  },
  {
    rowValue: [{ value: 'bill' }],
    filterValue: 'BILL',
    expected: true,
  },
]

const linkRowNotContainsCases = [
  {
    rowValue: [{ value: 'bill' }],
    filterValue: '',
    expected: true,
  },
  {
    rowValue: [{ value: 'bill' }],
    filterValue: 'bi',
    expected: false,
  },
  {
    rowValue: [{ value: 'some other name' }],
    filterValue: 'bill',
    expected: true,
  },
  {
    rowValue: [{ value: 'some other name' }, { value: 'bill' }],
    filterValue: 'bill',
    expected: false,
  },
  {
    rowValue: [{ value: 'BILL' }],
    filterValue: 'bill',
    expected: false,
  },
  {
    rowValue: [{ value: 'bill' }],
    filterValue: 'BILL',
    expected: false,
  },
]

export const dateDaysAfterValidCases = [
  {
    rowValue: moment.utc().subtract(5, 'days').format(),
    filterValue: 'UTC?10',
    expected: true,
  },
  {
    rowValue: moment.utc().subtract(10, 'days').format(),
    filterValue: 'UTC?10',
    expected: true,
  },
  {
    rowValue: moment.utc().subtract(21, 'days').format(),
    filterValue: 'UTC?30',
    expected: true,
  },
  {
    rowValue: moment.utc().subtract(10, 'days').add(5, 'hours').format(),
    filterValue: 'Europe/Berlin?10',
    expected: true,
  },
]

export const dateDaysAfterInvalidCases = [
  {
    rowValue: moment.utc().subtract(15, 'days').format(),
    filterValue: 'UTC?10',
    expected: false,
  },
  {
    rowValue: null,
    filterValue: 'UTC?15',
    expected: false,
  },
  {
    rowValue: moment.utc().subtract(5, 'days').format(),
    filterValue: 'UTC?-10',
    expected: false,
  },
  {
    rowValue: moment.utc().subtract(20, 'days').format(),
    filterValue: 'Europe/Berlin?10',
    expected: false,
  },
  {
    rowValue: moment.utc().subtract(10, 'days').add(5, 'hours').format(),
    filterValue: 'UTC?abc',
    expected: false,
  },
  {
    rowValue: moment.utc().subtract(10, 'days').add(5, 'hours').format(),
    filterValue: 'UTC? ',
    expected: false,
  },
]

// When this filter is applied, it should return even AND whole numbers:
const numberIsEvenAndWholeCases = [
  {
    rowValue: 2,
    expected: true,
  },
  {
    rowValue: 2.2,
    expected: false,
  },
  {
    rowValue: 3.0,
    expected: false,
  },
  {
    rowValue: 3.3,
    expected: false,
  },
  {
    rowValue: 4.0,
    expected: true,
  },
  {
    rowValue: null,
    expected: false,
  },
]

const durationHigherLowerThanCases = [
  {
    rowValue: null,
    filterValue: '1:01',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expectedGte: false,
    expectedGt: false,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 60,
    filterValue: '0:01', // will parse to one minute
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expectedGte: true,
    expectedGt: false,
    expectedLte: true,
    expectedLt: false,
  },
  {
    rowValue: 59,
    filterValue: '0:01', // will parse to one minute
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expectedGte: false,
    expectedGt: false,
    expectedLte: true,
    expectedLt: true,
  },
  {
    rowValue: 59,
    filterValue: '1:00', // will parse to one minute
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expectedGte: false,
    expectedGt: false,
    expectedLte: true,
    expectedLt: true,
  },

  {
    rowValue: 60,
    filterValue: '0:01', // will parse to one second
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expectedGte: true,
    expectedGt: true,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 120, // 2m
    filterValue: '0:01', // one minute
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expectedGte: true,
    expectedGt: true,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 61,
    filterValue: '60', // one minute
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expectedGte: true,
    expectedGt: true,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 61,
    filterValue: '60', // one minute
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expectedGte: true,
    expectedGt: true,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 86401,
    filterValue: '24:00:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expectedGte: true,
    expectedGt: true,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 86401, // 1d 1s
    filterValue: '86401', // 1d 1s
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expectedGte: true,
    expectedGt: false,
    expectedLte: true,
    expectedLt: false,
  },

  {
    rowValue: 86399,
    filterValue: '24:00:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expectedGte: false,
    expectedGt: false,
    expectedLte: true,
    expectedLt: true,
  },
  {
    rowValue: 86399, // exact
    filterValue: '86399', // exact
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expectedGte: true,
    expectedGt: false,
    expectedLte: true,
    expectedLt: false,
  },
  {
    rowValue: 86399,
    filterValue: '24:00:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'd h',
      },
    },
    expectedGte: false,
    expectedGt: false,
    expectedLte: true,
    expectedLt: true,
  },

  {
    rowValue: 86401,
    filterValue: '24:00:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'd h',
      },
    },
    expectedGte: true,
    expectedGt: true,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 86401,
    filterValue: '86401', // 24h
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'd h',
      },
    },
    expectedGte: true,
    expectedGt: true,
    expectedLte: false,
    expectedLt: false,
  },
  {
    rowValue: 86400,
    filterValue: '24:00:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'd h',
      },
    },
    expectedGte: true,
    expectedGt: false,
    expectedLte: true,
    expectedLt: false,
  },
  {
    rowValue: 86400,
    filterValue: '86399', // 24h
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'd h',
      },
    },
    expectedGte: true,
    expectedGt: false,
    expectedLte: true,
    expectedLt: false,
  },
]

const durationEmptyNotEmptyCases = [
  {
    rowValue: null,
    filterValue: '',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    emptyExpected: true,
    notEmptyExpected: false,
  },
  {
    rowValue: '',
    filterValue: '',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    emptyExpected: true,
    notEmptyExpected: false,
  },
  {
    rowValue: 1234,
    filterValue: '',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    emptyExpected: false,
    notEmptyExpected: true,
  },
]

const durationEqualToValueCases = [
  {
    rowValue: null,
    filterValue: '1:01',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expected: false,
  },
  {
    rowValue: 20 * 60, // 20 min
    filterValue: '0:01', // 1 min
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expected: false,
  },
  {
    rowValue: 61,
    filterValue: '0:01', // 1 min
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expected: false,
  },
  {
    rowValue: 20 * 60,
    filterValue: '0:20',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expected: true,
  },
  {
    rowValue: 20 * 60 - 1,
    filterValue: '0:20',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expected: false,
  },
  {
    rowValue: 20 * 60 - 1,
    filterValue: '0:20:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expected: false,
  },

  {
    rowValue: 61,
    filterValue: 60,
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expected: false,
  },
  {
    rowValue: 1234,
    filterValue: 1234,
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expected: true,
  },
  {
    rowValue: 86399, // 24h -1s
    filterValue: '24:00:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expected: false,
  },
  {
    rowValue: 86399,
    filterValue: '86400',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expected: false,
  },
  {
    rowValue: 86399,
    filterValue: '86400',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'd h',
      },
    },
    expected: false,
  },
  {
    rowValue: 86400,
    filterValue: '86402',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'd h',
      },
    },
    expected: true,
  },

  {
    rowValue: 86399,
    filterValue: '86399',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm:ss',
      },
    },
    expected: true,
  },
  {
    rowValue: 86399,
    filterValue: '24:00:00',
    context: {
      field: {
        type: 'formula',
        formula_type: 'duration',
        duration_format: 'h:mm',
      },
    },
    expected: false,
  },
]

const numberValueIsHigherThanCases = [
  {
    rowValue: 2,
    filterValue: 0,
    expected: true,
  },
  {
    rowValue: null,
    filterValue: 0,
    expected: false,
  },
  {
    rowValue: 0,
    filterValue: '0',
    expected: false,
  },
]

const numberValueIsHigherThanOrEqualCases = [
  {
    rowValue: 2,
    filterValue: 3,
    expected: false,
  },
  {
    rowValue: 2,
    filterValue: 0,
    expected: true,
  },
  {
    rowValue: null,
    filterValue: 0,
    expected: false,
  },
  {
    rowValue: 1,
    filterValue: '-1',
    expected: true,
  },
  {
    rowValue: 0,
    filterValue: '0',
    expected: true,
  },
  {
    rowValue: -1,
    filterValue: '-1',
    expected: true,
  },
  {
    rowValue: -1,
    filterValue: '0',
    expected: false,
  },
]

const numberValueIsLowerThanCases = [
  {
    rowValue: 1,
    filterValue: '2',
    expected: true,
  },
  {
    rowValue: null,
    filterValue: 0,
    expected: false,
  },
  {
    rowValue: 0,
    filterValue: '0',
    expected: false,
  },
]

const numberValueIsLowerThanOrEqualCases = [
  {
    rowValue: 2,
    filterValue: 3,
    expected: true,
  },
  {
    rowValue: 2,
    filterValue: 0,
    expected: false,
  },
  {
    rowValue: null,
    filterValue: 0,
    expected: false,
  },
  {
    rowValue: 1,
    filterValue: '-1',
    expected: false,
  },
  {
    rowValue: 0,
    filterValue: '0',
    expected: true,
  },
  {
    rowValue: -1,
    filterValue: '-1',
    expected: true,
  },
  {
    rowValue: -1,
    filterValue: '0',
    expected: true,
  },
]

const formulaUrlFieldEmptyCases = [
  { filterType: 'empty', filterValue: null, expectedResult: false },
  {
    filterType: 'empty',
    rowValue: '',
    filterValue: null,
    expectedResult: true,
  },
]

const formulaUrlFieldNotEmptyCases = [
  { filterType: 'not_empty', filterValue: null, expectedResult: true },
  {
    filterType: 'not_empty',
    rowValue: '',
    filterValue: null,
    expectedResult: false,
  },
]

const formulaUrlFieldFilterEqualCases = [
  {
    filterType: 'equal',
    filterValue: 'http://example.com/foo/bar',
    expectedResult: true,
  },
  {
    filterType: 'equal',
    filterValue: 'http://example.com/foobar',
    expectedResult: false,
  },
]

const formulaUrlFieldFilterContainsCases = [
  {
    filterType: 'contains',
    filterValue: 'foobar',
    expectedResult: false,
  },
  {
    filterType: 'contains',
    filterValue: 'foo/bar',
    expectedResult: true,
  },
]

const formulaUrlFieldFilterContainsWordCases = [
  {
    filterType: 'contains_word',
    filterValue: 'foo',
    expectedResult: true,
  },
  {
    filterType: 'contains_word',
    filterValue: 'foobar',
    expectedResult: false,
  },
]
const formulaUrlFieldFilterLengthIsLowerThanCases = [
  {
    filterType: 'length_is_lower_than',
    filterValue: '3',
    expectedResult: false,
  },
  {
    filterType: 'length_is_lower_than',
    filterValue: '30',
    expectedResult: true,
  },
]
const formulaUrlFieldFilterDoesntContainWordCases = [
  {
    filterType: 'doesnt_contain_word',
    filterValue: 'foobar',
    expectedResult: true,
  },
  {
    filterType: 'doesnt_contain_word',
    filterValue: 'foo',
    expectedResult: false,
  },
  {
    filterType: 'doesnt_contain_word',
    filterValue: 'foo',
    expectedResult: false,
  },
]

const formulaUrlFieldFilterDoesNotContainCases = [
  {
    filterType: 'contains_not',
    filterValue: 'foobar',
    expectedResult: true,
  },
  {
    filterType: 'contains_not',
    filterValue: 'foo/bar',
    expectedResult: false,
  },
]

const formulaUrlFieldFilterNotEqualCases = [
  {
    filterType: 'not_equal',
    filterValue: 'http://example.com/foo/bar',
    expectedResult: false,
  },
  {
    filterType: 'not_equal',
    filterValue: 'http://example.com/foobar',
    expectedResult: true,
  },
]

const booleanFieldTests = [
  {
    filterValue: null,
    rowValue: null,
    expectedResult: true, // both will evaluate to false
  },
  {
    filterValue: null,
    rowValue: '',
    expectedResult: true, // both will evaluate to false
  },
  {
    filterValue: '',
    rowValue: '',
    expectedResult: true, // both will evaluate to false
  },
  {
    filterValue: false,
    rowValue: true,
    expectedResult: false,
  },
  {
    filterValue: '0',
    rowValue: '0',
    expectedResult: true,
  },
  {
    filterValue: '1',
    rowValue: '0',
    expectedResult: false,
  },
  {
    filterValue: '1',
    rowValue: '1',
    expectedResult: true,
  },
]

describe('All Tests', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })
  afterEach(() => {
    testApp.afterEach()
  })

  test.each(dateBeforeCases)('(DEPRECATED) BeforeViewFilter', (values) => {
    const result = new DateBeforeViewFilterType({ app: testApp }).matches(
      values.rowValue,
      values.filterValue,
      { date_include_time: true }
    )
    expect(result).toBe(values.expected)
  })

  test.each(dateBeforeCases)('BeforeViewFilter', (values) => {
    const result = new DateIsBeforeMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateBeforeOrEqualCases)(
    '(DEPRECATED) BeforeOrEqualViewFilter',
    (values) => {
      const result = new DateBeforeOrEqualViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, {
        date_include_time: true,
      })
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateBeforeOrEqualCases)('BeforeOrEqualViewFilter', (values) => {
    const result = new DateIsOnOrBeforeMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateAfterCases)('(DEPRECATED) AfterViewFilter', (values) => {
    const result = new DateAfterViewFilterType({ app: testApp }).matches(
      values.rowValue,
      values.filterValue,
      { date_include_time: true }
    )
    expect(result).toBe(values.expected)
  })

  test.each(dateAfterCases)('AfterViewFilter', (values) => {
    const result = new DateIsAfterMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateAfterOrEqualCases)(
    '(DEPRECATED) AfterOrEqualViewFilter',
    (values) => {
      const result = new DateAfterOrEqualViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, {
        date_include_time: true,
      })
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateAfterOrEqualCases)('AfterOrEqualViewFilter', (values) => {
    const result = new DateIsAfterMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateEqualCases)('(DEPRECATED) DateEqual', (values) => {
    const result = new DateEqualViewFilterType({ app: testApp }).matches(
      values.rowValue,
      values.filterValue,
      { date_include_time: true }
    )
    expect(result).toBe(values.expected)
  })

  test.each(dateEqualCases)('DateEqual', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateNotEqualCases)('(DEPRECATED) DateNotEqual', (values) => {
    const result = new DateNotEqualViewFilterType({ app: testApp }).matches(
      values.rowValue,
      values.filterValue,
      { date_include_time: true }
    )

    expect(result).toBe(values.expected)
  })

  test.each(dateNotEqualCases)('DateNotEqual', (values) => {
    const result = new DateIsNotEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateToday)('(DEPRECATED) DateToday', (values) => {
    const result = new DateEqualsTodayViewFilterType({ app: testApp }).matches(
      values.rowValue,
      values.filterValue,
      {}
    )
    expect(result).toBe(values.expected)
  })

  test.each(dateToday)('DateToday', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}??today`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateBeforeToday)('(DEPRECATED) DateBeforeToday', (values) => {
    const result = new DateBeforeTodayViewFilterType({ app: testApp }).matches(
      values.rowValue,
      values.filterValue,
      {}
    )
    expect(result).toBe(values.expected)
  })

  test.each(dateBeforeToday)('DateBeforeToday', (values) => {
    const result = new DateIsBeforeMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}??today`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateAfterToday)('(DEPRECATED) DateAfterToday', (values) => {
    const result = new DateAfterTodayViewFilterType({ app: testApp }).matches(
      values.rowValue,
      values.filterValue,
      {}
    )
    expect(result).toBe(values.expected)
  })

  test.each(dateAfterToday)('DateAfterToday', (values) => {
    const result = new DateIsAfterMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}??today`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinDays)('(DEPRECATED) DateWithinDays', (values) => {
    const result = new DateWithinDaysViewFilterType({
      app: testApp,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinDays)('DateWithinDays', (values) => {
    const result = new DateIsWithinMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?nr_days_from_now`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinWeeks)('(DEPRECATED) DateWithinWeeks', (values) => {
    const result = new DateWithinWeeksViewFilterType({
      app: testApp,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinWeeks)('DateWithinWeeks', (values) => {
    const result = new DateWithinWeeksViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?nr_weeks_from_now`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinMonths)('(DEPRECATED) DateWithinMonths', (values) => {
    const result = new DateWithinMonthsViewFilterType({
      app: testApp,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinMonths)('DateWithinMonths', (values) => {
    const result = new DateWithinMonthsViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?nr_months_from_now`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateDaysAgo)('(DEPRECATED) DateDaysAgo', (values) => {
    const result = new DateEqualsDaysAgoViewFilterType({
      app: testApp,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateDaysAgo)('DateDaysAgo', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?nr_days_ago`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateMonthsAgo)('DateMonthsAgo', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?nr_months_ago`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateYearsAgo)('(DEPRECATED) DateYearsAgo', (values) => {
    const result = new DateEqualsYearsAgoViewFilterType({
      app: testApp,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateYearsAgo)('DateYearsAgo', (values) => {
    const result = new DateIsEqualMultiStepViewFilterType({
      app: testApp,
    }).matches(values.rowValue, `${values.filterValue}?nr_years_ago`, {})
    expect(result).toBe(values.expected)
  })

  test.each(multipleSelectValuesHas)('MultipleSelect Has', (values) => {
    const fieldType = new MultipleSelectFieldType()
    const result = new MultipleSelectHasFilterType({
      app: testApp._app,
    }).matches(values.rowValue, values.filterValue, {}, fieldType)
    expect(result).toBe(values.expected)
  })

  test.each(multipleSelectValuesHasNot)('MultipleSelect Has Not', (values) => {
    const result = new MultipleSelectHasNotFilterType({
      app: testApp._app,
    }).matches(values.rowValue, values.filterValue, {})
    expect(result).toBe(values.expected)
  })

  test.each(lengthIsLowerThanCases)(
    'LengthIsLowerThanViewFilterType',
    (values) => {
      const result = new LengthIsLowerThanViewFilterType().matches(
        values.rowValue,
        values.filterValue
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(linkRowContainsCases)('LinkRowContainsFilterType', (values) => {
    const result = new LinkRowContainsFilterType().matches(
      values.rowValue,
      values.filterValue
    )
    expect(result).toBe(values.expected)
  })

  test.each(linkRowNotContainsCases)(
    'LinkRowNotContainsFilterType',
    (values) => {
      const result = new LinkRowNotContainsFilterType().matches(
        values.rowValue,
        values.filterValue
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateDaysAfterValidCases)(
    '(DEPRECATED) DateDaysAfterValidFilterType',
    (values) => {
      const result = new DateAfterDaysAgoViewFilterType().matches(
        values.rowValue,
        values.filterValue
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateDaysAfterValidCases)(
    'DateDaysAfterValidFilterType',
    (values) => {
      const result = new DateIsOnOrAfterMultiStepViewFilterType().matches(
        values.rowValue,
        `${values.filterValue}?nr_days_ago`
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateDaysAfterInvalidCases)(
    '(DEPRECATED) DateDaysAfterInvalidFilterType',
    (values) => {
      const result = new DateAfterDaysAgoViewFilterType().matches(
        values.rowValue,
        values.filterValue
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateDaysAfterInvalidCases)(
    'DateDaysAfterInvalidFilterType',
    (values) => {
      const result = new DateIsOnOrAfterMultiStepViewFilterType().matches(
        values.rowValue,
        `${values.filterValue}?nr_days_ago`
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(numberIsEvenAndWholeCases)(
    'IsEvenAndWholeViewFilterType',
    (values) => {
      const result = new IsEvenAndWholeViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, {})
      expect(result).toBe(values.expected)
    }
  )

  test('HasFileType contains image', () => {
    expect(new HasFileTypeViewFilterType().matches([], '', {})).toBe(true)
    expect(new HasFileTypeViewFilterType().matches([], 'image', {})).toBe(false)
    expect(new HasFileTypeViewFilterType().matches([], 'document', {})).toBe(
      false
    )
    expect(
      new HasFileTypeViewFilterType().matches([{ is_image: true }], 'image', {})
    ).toBe(true)
    expect(
      new HasFileTypeViewFilterType().matches(
        [{ is_image: true }],
        'document',
        {}
      )
    ).toBe(false)
    expect(
      new HasFileTypeViewFilterType().matches(
        [{ is_image: false }],
        'image',
        {}
      )
    ).toBe(false)
    expect(
      new HasFileTypeViewFilterType().matches(
        [{ is_image: false }],
        'document',
        {}
      )
    ).toBe(true)
    expect(
      new HasFileTypeViewFilterType().matches(
        [{ is_image: true }, { is_image: false }],
        'image',
        {}
      )
    ).toBe(true)
    expect(
      new HasFileTypeViewFilterType().matches(
        [{ is_image: true }, { is_image: false }],
        'document',
        {}
      )
    ).toBe(true)
  })

  test('FilesLowerThanFilterType', () => {
    expect(new FilesLowerThanViewFilterType().matches([], 0)).toBe(false)
    expect(
      new FilesLowerThanViewFilterType().matches(
        [
          { visible_name: 'test_file_1.txt' },
          { visible_name: 'test_file_2.txt' },
        ],
        2
      )
    ).toBe(false)
    expect(
      new FilesLowerThanViewFilterType().matches(
        [
          { visible_name: 'test_file_1.txt' },
          { visible_name: 'test_file_2.txt' },
        ],
        3
      )
    ).toBe(true)
  })

  test.each(durationEmptyNotEmptyCases)(
    'durationEmptyNotEmptyCases empty test on duration formula field: %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new FormulaFieldType({ app })
      const { field } = values.context
      const result = new EmptyViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.emptyExpected)
    }
  )

  test.each(durationEmptyNotEmptyCases)(
    'durationEmptyNotEmptyCases not empty test on duration formula field: %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new FormulaFieldType({ app })
      const { field } = values.context
      const result = new NotEmptyViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.notEmptyExpected)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationHigherThanFilterType duration field %j',
    (values) => {
      const fieldType = new DurationFieldType({
        app: testApp,
      })
      const { field } = values.context
      const result = new HigherThanViewFilterType({ app: testApp }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expectedGt)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationHigherThanFilterType on duration formula field %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new FormulaFieldType({ app })
      const { field } = values.context
      field.formula_type = 'duration'
      const result = new HigherThanViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expectedGt)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationHigherOrEqualThanFilterType %j',
    (values) => {
      const fieldType = new DurationFieldType({
        app: testApp,
      })
      const { field } = values.context
      const result = new HigherThanOrEqualViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(values.expectedGte)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationHigherThanOrEqualFilterType on duration formula field %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new FormulaFieldType({ app })
      const { field } = values.context
      field.formula_type = 'duration'
      const result = new HigherThanOrEqualViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expectedGte)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationLowerThanFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new DurationFieldType({ app })
      const { field } = values.context
      const result = new LowerThanViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expectedLt)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationLowerThanFilterType on duration formula field %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new FormulaFieldType({ app })
      const { field } = values.context
      field.formula_type = 'duration'
      const result = new LowerThanViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expectedLt)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationLowerThanOrEqualFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new DurationFieldType({ app })
      const { field } = values.context
      const result = new LowerThanOrEqualViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expectedLte)
    }
  )

  test.each(durationHigherLowerThanCases)(
    'DurationLowerThanOrEqualFilterType on duration formula field %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new FormulaFieldType({ app })
      const { field } = values.context
      field.formula_type = 'duration'
      const result = new LowerThanOrEqualViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expectedLte)
    }
  )

  test.each(durationEqualToValueCases)(
    'durationEqualToValueCases on duration formula field: %j',
    (values) => {
      const app = testApp.getApp()
      const fieldType = new FormulaFieldType({ app })
      const { field } = values.context
      field.formula_type = 'duration'
      const result = new EqualViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(numberValueIsHigherThanCases)(
    'NumberHigherThanFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const result = new HigherThanViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        { type: 'number' },
        new NumberFieldType({ app })
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(numberValueIsHigherThanOrEqualCases)(
    'NumberHigherThanOrEqualFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const result = new HigherThanOrEqualViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        { type: 'number' },
        new NumberFieldType({ app })
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(numberValueIsHigherThanCases)(
    'FormulaNumberHigherThanFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const result = new HigherThanViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        { type: 'formula', formula_type: 'number' },
        new FormulaFieldType({ app })
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(numberValueIsLowerThanCases)(
    'NumberLowerThanFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const result = new LowerThanViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        { type: 'number' },
        new NumberFieldType({ app })
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(numberValueIsLowerThanOrEqualCases)(
    'NumberLowerThanOrEqualFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const result = new LowerThanOrEqualViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        { type: 'number' },
        new NumberFieldType({ app })
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(numberValueIsLowerThanCases)(
    'FormulaNumberLowerThanFilterType %j',
    (values) => {
      const app = testApp.getApp()
      const result = new LowerThanViewFilterType({ app }).matches(
        values.rowValue,
        values.filterValue,
        { type: 'formula', formula_type: 'number' },
        new FormulaFieldType({ app })
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(singleSelectValuesInFilterCases)(
    'SingleSelectIsAnyOfViewFilterType %j',
    (values) => {
      const fieldType = new SingleSelectFieldType()
      const field = {}
      const result = new SingleSelectIsAnyOfViewFilterType({
        app: testApp._app,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(values.is_any_of)
    }
  )

  test.each(singleSelectValuesInFilterCases)(
    'SingleSelectIsAnyOfViewFilterType %j',
    (values) => {
      const fieldType = new FormulaFieldType()
      const field = {
        formula_type: 'single_select',
      }
      const result = new SingleSelectIsAnyOfViewFilterType({
        app: testApp._app,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(values.is_any_of)
    }
  )

  test.each(singleSelectValuesInFilterCases)(
    'SingleSelectIsNoneOfViewFilterType %j',
    (values) => {
      const fieldType = new SingleSelectFieldType()
      const field = {}
      const result = new SingleSelectIsNoneOfViewFilterType({
        app: testApp._app,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(values.is_none_of)
    }
  )

  test.each(singleSelectValuesInFilterCases)(
    'SingleSelectIsNoneOfViewFilterType %j',
    (values) => {
      const fieldType = new FormulaFieldType()
      const field = {
        formula_type: 'single_select',
      }
      const result = new SingleSelectIsNoneOfViewFilterType({
        app: testApp._app,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(values.is_none_of)
    }
  )

  const runUrlFormulafieldTest = (values) => {
    const filterClass = testApp._app.$registry.get(
      'viewFilter',
      values.filterType
    )
    const fieldType = new FormulaFieldType({ app: testApp._app })
    const field = { formula_type: 'url', formula: '', type: 'formula' }
    const result = filterClass.matches(
      values.rowValue !== undefined
        ? values.rowValue
        : 'http://example.com/foo/bar',
      values.filterValue,
      field,
      fieldType
    )
    expect(result).toBe(values.expectedResult)
  }

  test.each(formulaUrlFieldEmptyCases)(
    'formulaUrlFieldFilters empty values test case',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldNotEmptyCases)(
    'formulaUrlFieldFilters not empty values test case %j',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldFilterEqualCases)(
    'formulaUrlFieldFilters equal test case %j',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldFilterNotEqualCases)(
    'formulaUrlFieldFilters not equal test case %j',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldFilterContainsCases)(
    'formulaUrlFieldFilters contains test case %j',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldFilterDoesNotContainCases)(
    'formulaUrlFieldFilters contains test case %j',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldFilterContainsWordCases)(
    'formulaUrlFieldFilters contains word test case %j',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldFilterDoesntContainWordCases)(
    'formulaUrlFieldFilters does not contain word test case %j',
    runUrlFormulafieldTest
  )

  test.each(formulaUrlFieldFilterLengthIsLowerThanCases)(
    'formulaUrlFieldFilters lenght is lower than test case %j',
    runUrlFormulafieldTest
  )

  test.each(booleanFieldTests)('Boolean filter type tests %j', (values) => {
    const result = new BooleanViewFilterType().matches(
      values.rowValue,
      values.filterValue,
      {}
    )
    expect(result).toBe(values.expectedResult)
  })
})

const MultipleCollaboratorsEmptyCases = [
  {
    filterType: 'empty',
    rowValue: [],
    filterValue: null,
    expected: true,
  },
  {
    filterType: 'empty',
    rowValue: [{ id: 1, name: 'foo' }],
    filterValue: null,
    expected: false,
  },
]

describe('Multiple collaborators view filters', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test.each(MultipleCollaboratorsEmptyCases)(
    'Multiple collaborators is empty.',
    (values) => {
      const fieldType = new MultipleCollaboratorsFieldType({ app: testApp })
      const field = { type: 'multiple_collaborators' }
      const result = new EmptyViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(values.expected)
    }
  )

  test.each(MultipleCollaboratorsEmptyCases)(
    'Multiple collaborators is not empty.',
    (values) => {
      const fieldType = new MultipleCollaboratorsFieldType({ app: testApp })
      const field = { type: 'multiple_collaborators' }
      const result = new NotEmptyViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(!values.expected)
    }
  )

  test.each(MultipleCollaboratorsEmptyCases)(
    'Multiple collaborators formula is empty.',
    (values) => {
      const field = {
        type: 'formula',
        formula_type: 'multiple_collaborators',
      }
      const fieldType = new FormulaFieldType({ app: testApp })
      const result = new EmptyViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(values.expected)
    }
  )

  test.each(MultipleCollaboratorsEmptyCases)(
    'Multiple collaborators formula is not empty.',
    (values) => {
      const field = {
        type: 'formula',
        formula_type: 'multiple_collaborators',
      }
      const fieldType = new FormulaFieldType({ app: testApp })
      const result = new NotEmptyViewFilterType({
        app: testApp,
      }).matches(values.rowValue, values.filterValue, field, fieldType)
      expect(result).toBe(!values.expected)
    }
  )
})

const emptyFilterValueCases = [
  {
    filterType: 'equal',
    rowValue: 'test',
    filterValue: '',
    expected: null,
  },
  {
    filterType: 'not_equal',
    rowValue: 'test',
    filterValue: '',
    expected: null,
  },
  {
    filterType: 'higher_than',
    rowValue: 5,
    filterValue: '',
    expected: null,
  },
  {
    filterType: 'higher_than_or_equal',
    rowValue: 5,
    filterValue: '',
    expected: null,
  },
  {
    filterType: 'lower_than',
    rowValue: 5,
    filterValue: '',
    expected: null,
  },
  {
    filterType: 'lower_than_or_equal',
    rowValue: 5,
    filterValue: '',
    expected: null,
  },
]

const emptyFilterValueSingleSelectCases = [
  {
    filterType: 'single_select_equal',
    rowValue: { id: 1, value: 'Option A', color: 'blue' },
    filterValue: '',
    expected: null,
  },
  {
    filterType: 'single_select_not_equal',
    rowValue: { id: 1, value: 'Option A', color: 'blue' },
    filterValue: '',
    expected: null,
  },
]

describe('Empty filter value tests', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test.each(emptyFilterValueCases)(
    'Filter type %s with empty value should return null',
    (values) => {
      const filterClass = testApp._app.$registry.get(
        'viewFilter',
        values.filterType
      )
      const result = filterClass.matches(
        values.rowValue,
        values.filterValue,
        { type: 'text' },
        {
          getMatchesParsedValues: (rowValue, filterValue) => ({
            rowVal: rowValue,
            filterVal: filterValue,
          }),
        }
      )
      expect(result).toBe(values.expected)
    }
  )

  test.each(emptyFilterValueSingleSelectCases)(
    'Filter type %s with empty value should return null',
    (values) => {
      const filterClass = testApp._app.$registry.get(
        'viewFilter',
        values.filterType
      )
      const result = filterClass.matches(
        values.rowValue,
        values.filterValue,
        { type: 'single_select' },
        {}
      )
      expect(result).toBe(values.expected)
    }
  )
})
