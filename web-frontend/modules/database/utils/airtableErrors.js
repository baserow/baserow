// These match the exception class names in the backend's
// `AirtableImportJobType.job_exceptions_map`, which are exposed via the
// `error_code` of a failed job.
export const AIRTABLE_BASE_REQUIRES_AUTHENTICATION =
  'AirtableBaseRequiresAuthentication'
export const AIRTABLE_BASE_NOT_PUBLIC = 'AirtableBaseNotPublic'

/**
 * Maps the machine readable error code of a failed Airtable import job to a
 * translated title and message that tells the user how to resolve the problem.
 * Falls back to the `human_readable_error` of the job for unmapped codes.
 */
export function getAirtableJobErrorMessage(t, job) {
  const errorMessages = {
    [AIRTABLE_BASE_REQUIRES_AUTHENTICATION]: {
      title: t('importFromAirtable.errorRequiresAuthenticationTitle'),
      message: t('importFromAirtable.errorRequiresAuthenticationDescription'),
    },
    [AIRTABLE_BASE_NOT_PUBLIC]: {
      title: t('importFromAirtable.errorBaseNotPublicTitle'),
      message: t('importFromAirtable.errorBaseNotPublicDescription'),
    },
  }
  return (
    errorMessages[job.error_code] || {
      title: t('importFromAirtable.importError'),
      message: job.human_readable_error,
    }
  )
}
