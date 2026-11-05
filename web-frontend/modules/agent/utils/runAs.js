import { RUN_AS_STATUS } from '@baserow/modules/agent/constants'

/** Keep the unavailable states distinct from intentionally unset access. */
export const getRunAsStatus = (runAs) =>
  runAs
    ? runAs.status ||
      (runAs.trashed ? RUN_AS_STATUS.TRASHED : RUN_AS_STATUS.ACTIVE)
    : RUN_AS_STATUS.UNSET
