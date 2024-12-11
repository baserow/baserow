<template>
  <div v-if="hasAtLeastOneLoginOption" :style="fullStyle">
    <template v-for="appAuthType in appAuthProviderTypes">
      <div
        v-if="hasAtLeastOneProvider(appAuthType)"
        :key="appAuthType.type"
        class="auth-form-element__provider"
      >
        <component
          :is="appAuthType.component"
          :user-source="selectedUserSource"
          :auth-providers="appAuthProviderPerTypes[appAuthType.type]"
          :login-button-label="resolvedLoginButtonLabel"
          @after-login="afterLogin"
        />
      </div>
    </template>
  </div>
  <p v-else>
    {{ $t('authFormElement.selectOrConfigureUserSourceFirst') }}
  </p>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import element from '@baserow/modules/builder/mixins/element'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { mapActions } from 'vuex'

export default {
  name: 'AuthFormElement',
  mixins: [element, form, error],
  inject: ['elementPage', 'builder'],
  props: {
    /**
     * @type {Object}
     * @property {number} user_source_id - The id of the user_source.
     * @property {string} login_button_label - The formula for the label of the login
     *   button
     */
    element: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {}
  },
  computed: {
    fullStyle() {
      return {
        ...this.getStyleOverride('input'),
        ...this.getStyleOverride('login_button'),
      }
    },
    selectedUserSource() {
      return this.$store.getters['userSource/getUserSourceById'](
        this.builder,
        this.element.user_source_id
      )
    },
    selectedUserSourceType() {
      if (!this.selectedUserSource) {
        return null
      }
      return this.$registry.get('userSource', this.selectedUserSource.type)
    },
    authProviders() {
      return this.selectedUserSource?.auth_providers || []
    },
    appAuthProviderTypes() {
      return this.$registry.getOrderedList('appAuthProvider')
    },
    appAuthProviderPerTypes() {
      return Object.fromEntries(
        this.appAuthProviderTypes.map((authType) => {
          return [
            authType.type,
            this.authProviders.filter(({ type }) => type === authType.type),
          ]
        })
      )
    },
    loginOptions() {
      if (!this.selectedUserSourceType) {
        return {}
      }
      return this.selectedUserSourceType.getLoginOptions(
        this.selectedUserSource
      )
    },
    hasAtLeastOneLoginOption() {
      return Object.keys(this.loginOptions).length > 0
    },
    resolvedLoginButtonLabel() {
      return (
        ensureString(this.resolveFormula(this.element.login_button_label)) ||
        this.$t('action.login')
      )
    },
  },
  watch: {
    userSource: {
      handler(newValue) {
        if (this.element.user_source_id) {
          const found = newValue.find(
            ({ id }) => id === this.element.user_source_id
          )
          if (!found) {
            // If the user_source has been removed we need to update the element
            this.actionForceUpdateElement({
              page: this.elementPage,
              element: this.element,
              values: { user_source_id: null },
            })
          }
        }
      },
    },
  },
  methods: {
    ...mapActions({
      actionForceUpdateElement: 'element/forceUpdate',
    }),
    hasAtLeastOneProvider(authProviderType) {
      return (
        this.appAuthProviderPerTypes[authProviderType.getType()]?.length > 0
      )
    },
    afterLogin() {
      this.fireEvent(
        this.elementType.getEventByName(this.element, 'after_login')
      )
    },
  },
}
</script>
