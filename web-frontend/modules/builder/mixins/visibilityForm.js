import UserSourceService from '@baserow/modules/core/services/userSource'

import {
  DEFAULT_USER_ROLE_PREFIX,
  ROLE_TYPE_ALLOW_ALL,
  ROLE_TYPE_ALLOW_EXCEPT,
  ROLE_TYPE_DISALLOW_EXCEPT,
  VISIBILITY_ALL,
  VISIBILITY_LOGGED_IN,
  VISIBILITY_NOT_LOGGED,
} from '@baserow/modules/builder/constants'

export default {
  inject: ['builder'],
  data() {
    return {
      allRoles: [],
      visibilityLoggedIn: VISIBILITY_LOGGED_IN,
      visibilityAll: VISIBILITY_ALL,
      visibilityNotLogged: VISIBILITY_NOT_LOGGED,
      loadingRoles: true,
    }
  },
  computed: {
    allowAllRolesExceptSelected() {
      return this.values.role_type === ROLE_TYPE_ALLOW_EXCEPT
    },

    disallowAllRolesExceptSelected() {
      return this.values.role_type === ROLE_TYPE_DISALLOW_EXCEPT
    },

    roleTypeOptions() {
      return {
        [ROLE_TYPE_ALLOW_ALL]: this.$t('visibilityForm.roleTypeAllowAllRoles'),
        [ROLE_TYPE_DISALLOW_EXCEPT]: this.$t(
          'visibilityForm.roleTypeDisallowAllRolesExcept'
        ),
        [ROLE_TYPE_ALLOW_EXCEPT]: this.$t(
          'visibilityForm.roleTypeAllowAllRolesExcept'
        ),
      }
    },

    userSources() {
      return this.$store.getters['userSource/getUserSources'](this.builder)
    },

    /**
     * When the user changes the role_type, e.g. 'Allow roles...',
     * reset the Page or Element roles.
     */
    selectedRoleType: {
      get() {
        return this.values.role_type
      },
      set(newValue) {
        this.values.role_type = newValue

        if (
          [ROLE_TYPE_ALLOW_EXCEPT, ROLE_TYPE_DISALLOW_EXCEPT].includes(newValue)
        ) {
          this.values.roles = []
        }
      },
    },

    /**
     * When the user changes the visibility, e.g. 'All visitors' radio button,
     * reset the Page or Element roles.
     */
    selectedVisibility: {
      get() {
        return this.values.visibility
      },
      set(newValue) {
        this.values.visibility = newValue
        this.resetElementRoles()
      },
    },
  },
  watch: {
    /**
     * If the userSource changes, we want to ensure the roles for the
     * Page/Element are still valid.
     */
    userSources: {
      handler() {
        this.fetchAndSyncUserRoles()
      },
      deep: true,
    },
  },
  async mounted() {
    await this.fetchAndSyncUserRoles()
  },
  methods: {
    checkRole(roleName) {
      if (this.values.roles.includes(roleName)) {
        this.values.roles = this.values.roles.filter(
          (role) => role !== roleName
        )
      } else {
        this.values.roles.push(roleName)
      }
    },

    isChecked(roleName) {
      return this.values.roles.includes(roleName)
    },

    async fetchAndSyncUserRoles() {
      await this.fetchUserRoles()
      this.syncUserRoles()
    },

    /**
     * Fetch all valid user roles.
     */
    async fetchUserRoles() {
      this.loadingRoles = true

      let result
      try {
        result = await UserSourceService(this.$client).fetchUserRoles(
          this.builder.id
        )
      } catch (error) {
        this.$store.dispatch('toast/error', {
          title: this.$t('visibilityForm.errorFetchingRolesTitle'),
          message: this.$t('visibilityForm.errorFetchingRolesMessage'),
        })
        return
      } finally {
        this.loadingRoles = false
      }

      let noRole = false
      let allRoles = Array.from(
        new Set(
          result.data
            .map((userSourceData) => {
              return userSourceData.roles.filter((role) => {
                if (role === '') {
                  noRole = true
                }
                return role !== ''
              })
            })
            .flat()
        )
      ).sort()

      // If noRole exists, prefix to array
      if (noRole) {
        allRoles = ['', ...allRoles]
      }

      this.allRoles = allRoles
    },

    getRoleName(roleName) {
      if (roleName === '') {
        return this.$t('visibilityForm.noRole')
      } else if (roleName.startsWith(DEFAULT_USER_ROLE_PREFIX)) {
        const userSourceId = parseInt(
          roleName.split(DEFAULT_USER_ROLE_PREFIX)[1]
        )
        const userSource = this.$store.getters['userSource/getUserSourceById'](
          this.builder,
          userSourceId
        )
        if (userSource) {
          return this.$t('visibilityForm.rolesAllMembersOf', {
            name: userSource.name,
          })
        }
      }

      return roleName
    },

    /**
     * Ensure that the roles of a Page or Element never contain any old or
     * otherwise invalid roles. This is done by getting the latest valid roles
     * from the backend and comparing it to the Page/Element roles.
     */
    syncUserRoles() {
      const validRoles = this.allRoles.filter((role) => {
        return this.values.roles.includes(role)
      })

      this.values.roles = validRoles
    },

    resetElementRoles() {
      this.values.roles = []
      this.values.role_type = ROLE_TYPE_ALLOW_ALL
    },

    selectAllRoles() {
      this.values.roles = [...this.allRoles]
    },

    deselectAllRoles() {
      this.values.roles = []
    },
  },
}
