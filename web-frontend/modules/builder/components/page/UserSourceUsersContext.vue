<template>
  <Context
    class="select user-source-users-context"
    :class="{ 'context--loading-overlay': state === 'loading' }"
    max-height-if-outside-viewport
    @shown="shown"
  >
    <SelectSearch
      v-model="search"
      :placeholder="$t('userSourceUsersContext.searchPlaceholder')"
    />
    <div v-auto-overflow-scroll class="user-source-users-context__user-list">
      <ul class="select__items select__items--no-max-height">
        <li
          class="select__item"
          :class="{
            'select__item--selected': !isAuthenticated,
            'select__item--loading':
              currentUser === null && state === 'loggingIn',
          }"
        >
          <a class="select__item-link">
            <Presentation
              :title="$t('userSourceUsersContext.anonymous')"
              size="medium"
              :initials="
                $t('userSourceUsersContext.anonymous') | nameAbbreviation
              "
              @click="selectUser()"
            />
          </a>
        </li>
        <template v-for="userSource in userSources">
          <template v-if="usersPerUserSources[userSource.id]?.length > 0">
            <li
              :key="`user_source_${userSource.id}`"
              class="select__item-label"
            >
              {{ userSource.name }}
            </li>
            <li
              v-for="user in usersPerUserSources[userSource.id]"
              :key="`user_source_${userSource.id}__${user.id}`"
              class="select__item"
              :class="{
                'select__item--selected': isSelectedUser(userSource, user),
                'select__item--loading':
                  isSelectedUser(userSource, user) && state === 'loggingIn',
              }"
            >
              <a class="select__item-link">
                <Presentation
                  :title="getUserTitle(user, userSource.name)"
                  :subtitle="user.email || $t('userSourceUsersContext.noEmail')"
                  size="medium"
                  :initials="
                    user.username ||
                    $t('userSourceUsersContext.unnamed') | nameAbbreviation
                  "
                  @click="selectUser(user)"
                />
              </a>
            </li>
          </template>
        </template>
      </ul>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { mapActions } from 'vuex'
import UserSourceService from '@baserow/modules/core/services/userSource'
import { notifyIf } from '@baserow/modules/core/utils/error'
import _ from 'lodash'
import { DEFAULT_USER_ROLE_PREFIX } from '@baserow/modules/builder/constants'

export default {
  name: 'UserSourceUsersContext',
  mixins: [context],
  inject: ['builder'],
  data() {
    return {
      state: null,
      search: '',
      currentUser: null,
      usersPerUserSources: {},
    }
  },
  computed: {
    isAuthenticated() {
      return this.$store.getters['userSourceUser/isAuthenticated'](this.builder)
    },
    loggedUser() {
      return this.$store.getters['userSourceUser/getUser'](this.builder)
    },
    userSources() {
      return this.$store.getters['userSource/getUserSources'](this.builder)
    },
  },
  watch: {
    search(newVal) {
      this.debouncedSearchUpdate(this, newVal)
    },
    /**
     * If the userSource changes, we want to ensure the User Roles in the
     * selector are still valid.
     */
    userSources: {
      handler() {
        this.refreshUserRoles()
      },
      deep: true,
    },
  },
  methods: {
    ...mapActions({
      actionForceAuthenticate: 'userSourceUser/forceAuthenticate',
      actionLogoff: 'userSourceUser/logoff',
    }),

    /**
     * When called, the authentication is forced which causes the
     * token to be refreshed. Since the user's role is in the token,
     * re-authenticating will cause the user's role to be also updated
     * in the context.
     */
    async refreshUserRoles() {
      if (!this.currentUser) {
        await this.actionLogoff({ application: this.builder })
      } else {
        const userSource = this.$store.getters['userSource/getUserSourceByUId'](
          this.builder,
          this.currentUser.user_source_uid
        )
        if (userSource) {
          await this.actionForceAuthenticate({
            application: this.builder,
            userSource,
            user: this.currentUser,
          })
        }
      }
    },

    getUserTitle(user, userSourceName) {
      const username =
        user.username || this.$t('userSourceUsersContext.unnamed')
      if (user.role.startsWith(DEFAULT_USER_ROLE_PREFIX)) {
        return this.$t('userSelector.member', {
          prefix: `${username} - ${userSourceName}`,
        })
      } else if (!user.role.trim().length) {
        return `${username} - ${this.$t('visibilityForm.noRole')}`
      } else {
        return `${username} - ${user.role}`
      }
    },

    async shown() {
      if (this.userSources.length === 0) {
        this.state = 'loaded'
        return
      }
      if (this.state !== 'loaded') {
        this.state = 'loading'
      }
      try {
        this.currentUser = this.loggedUser
        const {
          data: { users_per_user_sources: userSourceUsers },
        } = await UserSourceService(this.$client).getUserSourceUsers(
          this.builder.id
        )
        this.usersPerUserSources = userSourceUsers
      } catch (error) {
        this.state = 'error'
        notifyIf(error)
      }
      this.state = 'loaded'
    },

    isSelectedUser(userSource, user) {
      return (
        this.currentUser?.user_source_uid === userSource.uid &&
        this.currentUser?.id === user.id
      )
    },

    async selectUser(user) {
      this.state = 'loggingIn'
      const previousUser = this.currentUser
      this.currentUser = user
      try {
        if (!user) {
          await this.actionLogoff({ application: this.builder })
        } else {
          const userSource = this.$store.getters[
            'userSource/getUserSourceById'
          ](this.builder, user.user_source_id)
          await this.actionForceAuthenticate({
            application: this.builder,
            userSource,
            user,
          })
        }
      } catch {
        this.currentUser = previousUser
      } finally {
        this.state = 'loaded'
      }
      this.hide()
    },

    debouncedSearchUpdate: _.debounce(async (self, search) => {
      const {
        data: { users_per_user_sources: userSourceUsers },
      } = await UserSourceService(self.$client).getUserSourceUsers(
        self.builder.id,
        search
      )
      self.usersPerUserSources = userSourceUsers
    }, 300),
  },
}
</script>
