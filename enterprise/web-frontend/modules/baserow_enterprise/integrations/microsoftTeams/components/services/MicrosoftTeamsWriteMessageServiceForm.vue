<template>
  <form class="microsoft-teams-form" @submit.prevent>
    <Alert v-if="!values.integration_id" type="info-neutral">
      <p>{{ $t('microsoftTeamsForm.alertMessage') }}</p>
    </Alert>
    <FormGroup
      :label="$t('microsoftTeamsForm.integrationLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
        :service-types="[serviceType.getType()]"
      />
      <template v-if="integration?.account_email" #helper>
        {{
          $t('microsoftTeamsForm.sentAs', {
            name: integration.account_name || integration.account_email,
            email: integration.account_email,
          })
        }}
      </template>
    </FormGroup>

    <template v-if="integration">
      <Alert v-if="isPersonalAccount" type="error">
        <p>{{ $t('microsoftTeamsForm.personalAccount') }}</p>
      </Alert>
      <Alert v-else-if="needsAccess" type="warning">
        <template #title>{{
          integration.connected
            ? $t('microsoftTeamsForm.grantAccessTitle')
            : $t('microsoftTeamsForm.reconnectTitle')
        }}</template>
        <p>
          {{
            integration.connected
              ? $t('microsoftTeamsForm.grantAccessDescription')
              : $t('microsoftTeamsForm.reconnectDescription')
          }}
        </p>
        <template #actions>
          <Button
            type="secondary"
            :loading="signingIn"
            :disabled="signingIn"
            @click.prevent="grantAccess"
          >
            {{
              integration.connected
                ? $t('microsoftTeamsForm.grantAccess')
                : $t('microsoftTeamsForm.reconnect')
            }}
          </Button>
        </template>
      </Alert>
      <Alert v-if="signInError" type="error">
        <p>{{ signInError }}</p>
      </Alert>
    </template>

    <FormGroup
      :label="$t('microsoftTeamsForm.destinationLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <SegmentControl
        :segments="destinationSegments"
        :active-index="destinationIndex"
        size="small"
        @update:active-index="selectDestinationType"
      />
    </FormGroup>

    <template v-if="values.destination_type === DESTINATION_TYPE.CHANNEL">
      <FormGroup
        :label="$t('microsoftTeamsForm.teamLabel')"
        small-label
        required
        class="margin-bottom-2"
        :error-message="pickerErrors.teams"
      >
        <InjectedFormulaInput
          v-if="!pickable('team_id')"
          v-model="values.team_id"
          :placeholder="$t('microsoftTeamsForm.teamIdPlaceholder')"
        />
        <Dropdown
          v-else
          :value="literalFromFormula(values.team_id)"
          :loading="loading.teams"
          :placeholder="$t('microsoftTeamsForm.teamPlaceholder')"
          show-search
          @input="pickTeam"
        >
          <DropdownItem
            v-for="team in teamItems"
            :key="team.id"
            :name="team.name"
            :value="team.id"
          />
        </Dropdown>
        <!-- Always passed: FormGroup only checks its slots when mounted. -->
        <template #after-label>
          <a
            v-if="pickersAvailable"
            class="microsoft-teams-form__switch"
            @click.prevent="toggleFormula('team_id')"
          >
            {{ switchLabel('team_id') }}
          </a>
        </template>
      </FormGroup>

      <FormGroup
        :label="$t('microsoftTeamsForm.channelLabel')"
        small-label
        required
        class="margin-bottom-2"
        :error-message="pickerErrors.channels"
      >
        <InjectedFormulaInput
          v-if="!pickable('channel_id') || !pickedTeamId"
          v-model="values.channel_id"
          :placeholder="$t('microsoftTeamsForm.channelIdPlaceholder')"
        />
        <Dropdown
          v-else
          :value="literalFromFormula(values.channel_id)"
          :loading="loading.channels"
          :placeholder="$t('microsoftTeamsForm.channelPlaceholder')"
          show-search
          @input="pickChannel"
        >
          <DropdownItem
            v-for="channel in channelItems"
            :key="channel.id"
            :name="channel.name"
            :value="channel.id"
          />
        </Dropdown>
        <template #after-label>
          <a
            v-if="pickersAvailable && pickedTeamId"
            class="microsoft-teams-form__switch"
            @click.prevent="toggleFormula('channel_id')"
          >
            {{ switchLabel('channel_id') }}
          </a>
        </template>
      </FormGroup>
    </template>

    <FormGroup
      v-else
      :label="$t('microsoftTeamsForm.chatLabel')"
      small-label
      required
      class="margin-bottom-2"
      :error-message="pickerErrors.chats"
    >
      <InjectedFormulaInput
        v-if="!pickable('chat_id')"
        v-model="values.chat_id"
        :placeholder="$t('microsoftTeamsForm.chatIdPlaceholder')"
      />
      <Dropdown
        v-else
        :value="literalFromFormula(values.chat_id)"
        :loading="loading.chats"
        :placeholder="$t('microsoftTeamsForm.chatPlaceholder')"
        show-search
        @input="pickChat"
      >
        <DropdownItem
          v-for="chat in chatItems"
          :key="chat.id"
          :name="chat.name || $t('microsoftTeamsForm.unnamedChat')"
          :value="chat.id"
        />
      </Dropdown>
      <template #after-label>
        <a
          v-if="pickersAvailable"
          class="microsoft-teams-form__switch"
          @click.prevent="toggleFormula('chat_id')"
        >
          {{ switchLabel('chat_id') }}
        </a>
      </template>
    </FormGroup>

    <FormGroup
      :label="$t('microsoftTeamsForm.messageLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.message"
        :placeholder="$t('microsoftTeamsForm.messagePlaceholder')"
        textarea
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown.vue'
import { MicrosoftIntegrationType } from '@baserow/modules/integrations/microsoft/integrationTypes'
import {
  OAuthSignInError,
  openOAuthSignInPopup,
  useOAuthSignIn,
} from '@baserow/modules/integrations/oauthAccount/composables/useOAuthSignIn'
import { OAUTH_ERROR_CODE } from '@baserow/modules/integrations/oauthAccount/constants'
import { oauthErrorMessage } from '@baserow/modules/integrations/oauthAccount/utils'
import MicrosoftTeamsService from '@baserow_enterprise/integrations/microsoftTeams/services/microsoftTeams'
import {
  DESTINATION_TYPE,
  formulaForLiteral,
  isFormulaEmpty,
  literalFromFormula,
} from '@baserow_enterprise/integrations/microsoftTeams/utils'

/**
 * Sends a Teams message as the account of a Microsoft integration. The team,
 * channel or chat is picked from the account's own, or given as an id or a
 * formula for a destination that depends on data.
 */
export default {
  name: 'MicrosoftTeamsWriteMessageServiceForm',
  components: { IntegrationDropdown, InjectedFormulaInput },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { oauth: useOAuthSignIn(MicrosoftIntegrationType.getType()) }
  },
  data() {
    return {
      DESTINATION_TYPE,
      allowedValues: [
        'integration_id',
        'destination_type',
        'team_id',
        'channel_id',
        'chat_id',
        'destination_label',
        'message',
      ],
      values: {
        integration_id: null,
        destination_type: DESTINATION_TYPE.CHANNEL,
        team_id: { formula: '', mode: 'simple' },
        channel_id: { formula: '', mode: 'simple' },
        chat_id: { formula: '', mode: 'simple' },
        destination_label: '',
        message: { formula: '', mode: 'simple' },
      },
      // How the person switched an id field: true for an id or a formula,
      // false for the list. Fields not switched follow their value.
      formulaToggles: {},
      // The latest request of each list, so a slower, older answer can't
      // replace it.
      requestCount: 0,
      latestRequests: {},
      teams: [],
      channels: [],
      chats: [],
      loading: { teams: false, channels: false, chats: false },
      pickerErrors: { teams: '', channels: '', chats: '' },
      signingIn: false,
      signInError: '',
      // The integration access was granted to from this form. The service's
      // `missing_scopes` only catches up when it's saved again.
      grantedIntegrationId: null,
    }
  },
  computed: {
    serviceType() {
      return this.$registry.get('service', 'microsoft_teams_write_message')
    },
    integrationType() {
      return this.serviceType.integrationType
    },
    integrations() {
      return this.$store.getters['integration/getIntegrations'](
        this.application
      ).filter(({ type }) => type === this.integrationType.type)
    },
    integration() {
      return (
        this.integrations.find(({ id }) => id === this.values.integration_id) ||
        null
      )
    },
    isPersonalAccount() {
      return this.integration?.account_type === 'personal'
    },
    needsAccess() {
      if (!this.integration) return false
      if (!this.integration.connected) return true
      // The backend says which permissions are missing, for the integration
      // the service was saved with.
      return (
        this.grantedIntegrationId !== this.integration.id &&
        this.defaultValues.integration_id === this.integration.id &&
        (this.defaultValues.missing_scopes || []).length > 0
      )
    },
    /** Whether the account can list its teams, channels and chats. */
    pickersAvailable() {
      return Boolean(
        this.integration && !this.isPersonalAccount && !this.needsAccess
      )
    },
    destinationSegments() {
      return [
        {
          value: DESTINATION_TYPE.CHANNEL,
          label: this.$t('microsoftTeamsForm.channel'),
        },
        {
          value: DESTINATION_TYPE.CHAT,
          label: this.$t('microsoftTeamsForm.chat'),
        },
      ]
    },
    destinationIndex() {
      return this.destinationSegments.findIndex(
        ({ value }) => value === this.values.destination_type
      )
    },
    pickedTeamId() {
      return this.pickable('team_id')
        ? literalFromFormula(this.values.team_id)
        : null
    },
    teamItems() {
      return this.withCurrent(this.teams, 'team_id')
    },
    channelItems() {
      return this.withCurrent(this.channels, 'channel_id')
    },
    chatItems() {
      return this.withCurrent(this.chats, 'chat_id')
    },
    /** What to load for the destination shown, given what's picked. */
    pickerKey() {
      if (!this.pickersAvailable) return null
      return [
        this.values.integration_id,
        this.values.destination_type,
        this.pickedTeamId,
      ].join('|')
    },
  },
  watch: {
    pickerKey: {
      handler(key, oldKey) {
        if (key && key !== oldKey) {
          this.loadPickers()
        }
      },
      immediate: true,
    },
    'values.integration_id'(id, oldId) {
      if (oldId !== undefined && id !== oldId) {
        this.teams = []
        this.channels = []
        this.chats = []
        this.loading = { teams: false, channels: false, chats: false }
        this.signInError = ''
      }
    },
  },
  methods: {
    literalFromFormula,
    /**
     * Whether an id field shows as an id or formula input: as switched, or,
     * when it wasn't, whenever its value is more than a picked id. Derived
     * from the value, so a formula restored by undo or typed before the lists
     * were available is never hidden behind a list.
     */
    isFormula(field) {
      if (field in this.formulaToggles) {
        return this.formulaToggles[field]
      }
      const formula = this.values[field]
      return !isFormulaEmpty(formula) && literalFromFormula(formula) === null
    },
    pickable(field) {
      return this.pickersAvailable && !this.isFormula(field)
    },
    switchLabel(field) {
      return this.isFormula(field)
        ? this.$t('microsoftTeamsForm.pickFromList')
        : this.$t('microsoftTeamsForm.useFormula')
    },
    toggleFormula(field) {
      const formula = !this.isFormula(field)
      this.formulaToggles = { ...this.formulaToggles, [field]: formula }
      // A label only names a picked destination.
      this.values.destination_label = ''
      if (!formula) {
        // Back to the list: an id typed meanwhile may not be in it.
        if (literalFromFormula(this.values[field]) === null) {
          this.values[field] = formulaForLiteral('')
        }
      }
    },
    /**
     * The loaded items, plus the picked one when it isn't among them, e.g.
     * while they load, named by the label the action keeps.
     */
    withCurrent(items, field) {
      const id = literalFromFormula(this.values[field])
      if (!id || items.some((item) => item.id === id)) {
        return items
      }
      const name =
        (field !== 'team_id' && this.values.destination_label) ||
        this.$t('microsoftTeamsForm.unknownItem')
      return [{ id, name }, ...items]
    },
    selectDestinationType(index) {
      const type = this.destinationSegments[index].value
      if (type !== this.values.destination_type) {
        this.values.destination_type = type
        this.values.destination_label = ''
      }
    },
    pickTeam(teamId) {
      if (teamId === literalFromFormula(this.values.team_id)) return
      this.values.team_id = formulaForLiteral(teamId)
      // The channel belongs to the team.
      this.values.channel_id = formulaForLiteral('')
      this.values.destination_label = ''
      this.channels = []
      // Another team's channels, should they still arrive, aren't this one's.
      this.latestRequests = { ...this.latestRequests, channels: null }
    },
    pickChannel(channelId) {
      const channel = this.channels.find(({ id }) => id === channelId)
      const team = this.teams.find(({ id }) => id === this.pickedTeamId)
      this.values.channel_id = formulaForLiteral(channelId)
      this.values.destination_label = [channel?.name, team?.name]
        .filter(Boolean)
        .join(' · ')
    },
    pickChat(chatId) {
      const chat = this.chats.find(({ id }) => id === chatId)
      this.values.chat_id = formulaForLiteral(chatId)
      this.values.destination_label = chat?.name || ''
    },
    async loadPickers() {
      const integrationId = this.values.integration_id
      const service = MicrosoftTeamsService(this.$client)
      if (this.values.destination_type === DESTINATION_TYPE.CHAT) {
        if (this.pickable('chat_id')) {
          await this.load('chats', () => service.listChats(integrationId))
        }
        return
      }
      if (this.pickable('team_id')) {
        await this.load('teams', () => service.listTeams(integrationId))
      }
      const teamId = this.pickedTeamId
      if (teamId && this.pickable('channel_id')) {
        await this.load('channels', () =>
          service.listChannels(integrationId, teamId)
        )
      }
    },
    async load(name, request) {
      this.requestCount += 1
      const requestId = this.requestCount
      const integrationId = this.values.integration_id
      this.latestRequests = { ...this.latestRequests, [name]: requestId }
      // Another account's list, or one asked for before, isn't this one.
      const isLatest = () =>
        this.latestRequests[name] === requestId &&
        this.values.integration_id === integrationId
      this.loading[name] = true
      this.pickerErrors[name] = ''
      try {
        const { data } = await request()
        if (isLatest()) {
          this[name] = data
        }
      } catch (error) {
        if (!error.handler) throw error
        error.handler.handled()
        if (isLatest()) {
          this[name] = []
          this.pickerErrors[name] =
            error.handler.detail || this.$t('microsoftTeamsForm.loadFailed')
        }
      } finally {
        if (isLatest()) {
          this.loading[name] = false
        }
      }
    },
    async grantAccess() {
      // Opened straight from the click, before any request, or it's blocked.
      const popup = openOAuthSignInPopup(this.integrationType.getType())
      this.signingIn = true
      this.signInError = ''
      const integrationId = this.integration.id
      try {
        await this.oauth.signIn({
          popup,
          application: this.application,
          integration: this.integration,
          serviceTypes: [this.serviceType.getType()],
        })
        this.grantedIntegrationId = integrationId
      } catch (error) {
        let code = null
        if (error instanceof OAuthSignInError) {
          code = error.code
        } else if (error.handler) {
          error.handler.handled()
          code = error.handler.code
        } else {
          throw error
        }
        if (code !== OAUTH_ERROR_CODE.SIGN_IN_CANCELLED) {
          this.signInError = oauthErrorMessage(
            this.$t,
            code,
            this.integrationType.providerName
          )
        }
      } finally {
        this.signingIn = false
      }
    },
  },
}
</script>
