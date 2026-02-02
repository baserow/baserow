import { TestApp } from '@baserow/test/helpers/testApp'
import _ from 'lodash'
import { PremiumLicenseType } from '@baserow_premium/licenseTypes'
import MockPremiumServer from '@baserow_premium_test/fixtures/mockPremiumServer'

export class PremiumTestApp extends TestApp {
  setupMockServer() {
    return new MockPremiumServer(this.mock, this.store)
  }

  createTestUserInAuthStore() {
    const fakeUserData = {
      user: {
        id: 256,
      },
      access_token:
        `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImpvaG5AZXhhb` +
        `XBsZS5jb20iLCJpYXQiOjE2NjAyOTEwODYsImV4cCI6MTY2MDI5NDY4NiwianRpIjo` +
        `iNDZmNzUwZWUtMTJhMS00N2UzLWJiNzQtMDIwYWM4Njg3YWMzIiwidXNlcl9pZCI6M` +
        `iwidXNlcl9wcm9maWxlX2lkIjpbMl0sIm9yaWdfaWF0IjoxNjYwMjkxMDg2fQ.RQ-M` +
        `NQdDR9zTi8CbbQkRrwNsyDa5CldQI83Uid1l9So`,
    }
    this.$store.dispatch('auth/forceSetUserData', {
      ...fakeUserData,
    })
    return fakeUserData
  }

  giveCurrentUserGlobalPremiumFeatures() {
    this.$store.dispatch('auth/forceUpdateUserData', {
      active_licenses: {
        instance_wide: { [PremiumLicenseType.getType()]: true },
      },
    })
  }

  giveCurrentUserPremiumFeatureForSpecificWorkspaceOnly(workspaceId) {
    this.$store.dispatch('auth/forceUpdateUserData', {
      active_licenses: {
        per_workspace: {
          workspaceId: { [PremiumLicenseType.getType()]: true },
        },
      },
    })
  }

  updateCurrentUserToBecomeStaffMember() {
    this.$store.dispatch('auth/forceUpdateUserData', {
      user: {
        is_staff: true,
      },
    })
  }
}
