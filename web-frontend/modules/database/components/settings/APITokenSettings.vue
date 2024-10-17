<template>
  <div class="api-token-settings">
    <template v-if="page === 'list'">
      <Error :error="error"></Error>
      <div v-if="listLoading" class="api-token-settings__loading">
        <div class="loading-spinner"></div>
      </div>

      <template v-else>
        <p v-if="tokens.length === 0">
          {{ $t('apiTokenSettings.noTokensMessage') }}
        </p>
        <APIToken
          v-for="token in tokens"
          :key="token.id"
          :token="token"
          @deleted="deleteToken(token.id)"
        ></APIToken>
        <div v-if="tokens.length > 0" class="margin-top-3">
          <SwitchInput :value="true" small class="margin-bottom-1">
            {{ $t('apiTokenSettings.hasFullPermissions') }}
          </SwitchInput>
          <SwitchInput :value="2" small class="margin-bottom-1">
            {{ $t('apiTokenSettings.hasOnlySelectedPermissions') }}
          </SwitchInput>
          <SwitchInput :value="false" small>
            {{ $t('apiTokenSettings.noPermissions') }}
          </SwitchInput>
        </div>
      </template>
    </template>
    <template v-else-if="page === 'create'">
      <Error :error="error"></Error>
      <APITokenForm ref="form" @submitted="create"> </APITokenForm>
    </template>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import APIToken from '@baserow/modules/database/components/settings/APIToken'
import APITokenForm from '@baserow/modules/database/components/settings/APITokenForm'
import TokenService from '@baserow/modules/database/services/token'

export default {
  name: 'APITokenSettings',
  components: { APIToken, APITokenForm },
  mixins: [error],
  data() {
    return {
      page: 'list',
      tokens: [],
      listLoading: true,
      createLoading: false,
    }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](1)
    },
  },
  watch: {
    page(newVal) {
      this.$emit('database-token-page-type-changed', newVal)
    },
  },
  /**
   * When the component is mounted we immediately want to fetch all the tokens.
   */
  async mounted() {
    try {
      const { data } = await TokenService(this.$client).fetchAll()
      this.tokens = data
      this.listLoading = false
    } catch (error) {
      this.listLoading = false
      this.handleError(error, 'token')
    }
  },
  methods: {
    /**
     * When the create token form is submitted the create method is called. It will
     * make a request to the backend asking to create a new token. The newly created
     * token is going to be added last.
     */
    async create(values) {
      this.$emit('loading', true)
      this.hideError()

      try {
        const { data } = await TokenService(this.$client).create(values)
        this.tokens.push(data)
        this.$emit('loading', false)
        this.page = 'list'
      } catch (error) {
        this.$emit('loading', false)
        this.handleError(error, 'token')
      }
    },
    /**
     * Called when a token is already deleted. It must then be removed from the list of
     * tokens.
     */
    deleteToken(tokenId) {
      const index = this.tokens.findIndex((token) => token.id === tokenId)
      this.tokens.splice(index, 1)
    },
    getCTALabel() {
      return this.$t('apiTokenSettings.createToken')
    },
    setPageType(pageType) {
      this.page = pageType
    },
    submitForm() {
      this.$refs.form.submit()
    },
  },
}
</script>
