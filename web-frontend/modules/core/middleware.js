import settings from '@baserow/modules/core/middleware/settings'
import authentication from '@baserow/modules/core/middleware/authentication'
import authenticated from '@baserow/modules/core/middleware/authenticated'
import staff from '@baserow/modules/core/middleware/staff'
import workspacesAndApplications from '@baserow/modules/core/middleware/workspacesAndApplications'
import pendingJobs from '@baserow/modules/core/middleware/pendingJobs'
import urlCheck from '@baserow/modules/core/middleware/urlCheck'
import impersonate from '@baserow/modules/core/middleware/impersonate'

/* eslint-disable-next-line */
import Middleware from './middleware'

Middleware.settings = settings
Middleware.authentication = authentication
Middleware.authenticated = authenticated
Middleware.staff = staff
Middleware.workspacesAndApplications = workspacesAndApplications
Middleware.pendingJobs = pendingJobs
Middleware.urlCheck = urlCheck
Middleware.impersonate = impersonate
