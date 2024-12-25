import { userCanViewPage } from '@baserow/modules/builder/utils/visibility'

import {
  VISIBILITY_ALL,
  VISIBILITY_LOGGED_IN,
  ROLE_TYPE_ALLOW_EXCEPT,
  ROLE_TYPE_DISALLOW_EXCEPT,
  ROLE_TYPE_ALLOW_ALL,
} from '@baserow/modules/builder/constants'

describe('userCanViewPage tests', () => {
  const testCasesVisibilityAll = [
    {
      userRole: '',
      isAuthenticated: false,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: false,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: ['fooRole'],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: ['fooRole'],
      pageRoleType: ROLE_TYPE_ALLOW_EXCEPT,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: ['fooRole'],
      pageRoleType: ROLE_TYPE_DISALLOW_EXCEPT,
    },
  ]
  test.each(testCasesVisibilityAll)(
    'Allow access if visibility is "all", regardless of other page visibility settings.',
    (testCase) => {
      const user = { role: testCase.userRole }
      const page = {
        visibility: VISIBILITY_ALL,
        role_type: testCase.pageRoleType,
        roles: testCase.pageRoles,
      }
      const result = userCanViewPage(user, testCase.isAuthenticated, page)
      expect(result).toEqual(true)
    }
  )

  const testCasesVisibilityLoggedIn = [
    {
      userRole: '',
      isAuthenticated: false,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
      expectedResult: false,
    },
    {
      userRole: '',
      isAuthenticated: false,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_EXCEPT,
      expectedResult: false,
    },
    {
      userRole: '',
      isAuthenticated: false,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_DISALLOW_EXCEPT,
      expectedResult: false,
    },
    {
      userRole: '',
      isAuthenticated: true,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
      expectedResult: true,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
      expectedResult: true,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: ['fooRole'],
      pageRoleType: ROLE_TYPE_ALLOW_ALL,
      expectedResult: true,
    },
    {
      userRole: '',
      isAuthenticated: true,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_EXCEPT,
      expectedResult: true,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_ALLOW_EXCEPT,
      expectedResult: true,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: ['fooRole'],
      pageRoleType: ROLE_TYPE_ALLOW_EXCEPT,
      expectedResult: false,
    },
    {
      userRole: '',
      isAuthenticated: true,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_DISALLOW_EXCEPT,
      expectedResult: false,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: [],
      pageRoleType: ROLE_TYPE_DISALLOW_EXCEPT,
      expectedResult: false,
    },
    {
      userRole: 'fooRole',
      isAuthenticated: true,
      pageRoles: ['fooRole'],
      pageRoleType: ROLE_TYPE_DISALLOW_EXCEPT,
      expectedResult: true,
    },
  ]
  test.each(testCasesVisibilityLoggedIn)(
    'Allow access if visibility is "logged-in" and page settings permit access.',
    (testCase) => {
      const user = { role: testCase.userRole }
      const page = {
        visibility: VISIBILITY_LOGGED_IN,
        role_type: testCase.pageRoleType,
        roles: testCase.pageRoles,
      }
      const result = userCanViewPage(user, testCase.isAuthenticated, page)
      expect(result).toEqual(testCase.expectedResult)
    }
  )
})
