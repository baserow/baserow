import { getAirtableJobErrorMessage } from '@baserow/modules/database/utils/airtableErrors'
import { AirtableDatabaseOnboardingStepType } from '@baserow/modules/database/databaseOnboardingStepTypes'

const fakeT = (key) => key
const fakeI18n = { t: fakeT }

describe('getAirtableJobErrorMessage', () => {
  test('maps the requires authentication error code', () => {
    const job = { error_code: 'AirtableBaseRequiresAuthentication' }
    expect(getAirtableJobErrorMessage(fakeT, job)).toStrictEqual({
      title: 'importFromAirtable.errorRequiresAuthenticationTitle',
      message: 'importFromAirtable.errorRequiresAuthenticationDescription',
    })
  })

  test('maps the base not public error code', () => {
    const job = { error_code: 'AirtableBaseNotPublic' }
    expect(getAirtableJobErrorMessage(fakeT, job)).toStrictEqual({
      title: 'importFromAirtable.errorBaseNotPublicTitle',
      message: 'importFromAirtable.errorBaseNotPublicDescription',
    })
  })

  test('falls back to the human readable error for unmapped error codes', () => {
    const job = {
      error_code: 'SoftTimeLimitExceeded',
      human_readable_error: 'The job took too long.',
    }
    expect(getAirtableJobErrorMessage(fakeT, job)).toStrictEqual({
      title: 'importFromAirtable.importError',
      message: 'The job took too long.',
    })
  })
})

describe('AirtableDatabaseOnboardingStepType.getJobErrorMessage', () => {
  const stepType = new AirtableDatabaseOnboardingStepType({
    app: { $i18n: fakeI18n },
  })

  test('returns the mapped message for a known error code', () => {
    const job = { error_code: 'AirtableBaseNotPublic' }
    expect(stepType.getJobErrorMessage(job, {}, {})).toStrictEqual({
      title: 'importFromAirtable.errorBaseNotPublicTitle',
      message: 'importFromAirtable.errorBaseNotPublicDescription',
    })
  })

  test('falls back to the human readable error for unknown codes', () => {
    const job = { error_code: '', human_readable_error: 'Custom failure' }
    expect(stepType.getJobErrorMessage(job, {}, {})).toStrictEqual({
      title: 'importFromAirtable.importError',
      message: 'Custom failure',
    })
  })
})
