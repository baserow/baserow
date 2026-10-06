<template>
  <div>
    <div class="agent-configuration__subsection">
      <div class="agent-configuration__subsection-title">
        {{ $t('agentTrigger.triggers') }}
      </div>
      <ButtonText
        v-if="!readOnly"
        icon="iconoir-plus"
        :loading="addLoading"
        :disabled="loading"
        @click="
          $refs.addTriggerContext.toggle(
            $event.currentTarget,
            'bottom',
            'right',
            4
          )
        "
      >
        {{ $t('agentTrigger.addTrigger') }}
      </ButtonText>
    </div>
    <div v-if="loading" class="loading"></div>
    <div
      v-else-if="triggers.length === 0"
      class="agent-configuration__placeholder"
    >
      {{ $t('agentTrigger.empty') }}
    </div>
    <div
      v-if="!application.active && triggers.length > 0"
      class="agent-configuration__paused-hint margin-bottom-2"
    >
      <i class="iconoir-pause"></i>
      {{ $t('agentTrigger.pausedHint') }}
    </div>
    <div
      v-if="!loading && triggers.length > 0"
      class="agent-configuration__card-list"
    >
      <AgentConfigurationCard
        v-for="trigger in triggers"
        :key="trigger.id"
        :title="triggerNodeTypeName(trigger)"
        :icon="triggerNodeTypeIcon(trigger)"
      >
        <template #header-right>
          <SwitchInput
            small
            :value="trigger.enabled"
            :disabled="readOnly"
            :title="$t('agentTrigger.enabledLabel')"
            @input="onEnabledChange(trigger, $event)"
          ></SwitchInput>
        </template>
        <ReadOnlyForm :read-only="readOnly">
          <AgentServiceForm
            v-if="triggerNodeType(trigger)"
            :key="serviceFormKey(trigger)"
            :application="application"
            :service-type="triggerNodeType(trigger).serviceType"
            :service="trigger.service || {}"
            @values-changed="onServiceValuesChanged(trigger, $event)"
          />
        </ReadOnlyForm>
        <div class="agent-configuration__hint">
          {{ $t('agentTrigger.hint') }}
        </div>
        <Expandable
          v-if="(trigger.tokens || []).length > 0"
          class="agent-configuration__trigger-data"
        >
          <template #header="{ toggle, expanded }">
            <a class="agent-configuration__expand-link" @click.prevent="toggle">
              <span>{{ $t('agentTrigger.dataItProvides') }}</span>
              <span class="agent-configuration__expand-count">
                {{
                  $t('agentTrigger.valuesCount', {
                    count: trigger.tokens.length,
                  })
                }}
              </span>
              <i
                class="agent-configuration__card-chevron iconoir-nav-arrow-down"
                :class="{
                  'agent-configuration__card-chevron--expanded': expanded,
                }"
              ></i>
            </a>
          </template>
          <div class="agent-configuration__expand-body">
            <div class="agent-configuration__token-list">
              <div
                v-for="token in trigger.tokens"
                :key="token.token"
                class="agent-configuration__token-row"
              >
                <span class="agent-configuration__token-description">
                  {{ token.description }}
                </span>
                <a
                  class="agent-configuration__token"
                  :title="$t('agentTrigger.copyToken')"
                  @click.prevent="copyToken(trigger, token)"
                >
                  <code>{{ token.token }}</code>
                  <Copied :ref="`copied-${trigger.id}-${token.token}`"></Copied>
                </a>
              </div>
            </div>
            <FormGroup
              v-if="trigger.sample_payload"
              small-label
              :label="$t('agentTrigger.examplePayload')"
              :helper-text="$t('agentTrigger.examplePayloadHelper')"
            >
              <pre class="agent-configuration__payload">{{
                formatPayload(trigger.sample_payload)
              }}</pre>
            </FormGroup>
          </div>
        </Expandable>
        <template v-if="!readOnly && canDeleteTrigger" #footer>
          <ButtonText
            icon="iconoir-bin"
            :loading="deletingIds.includes(trigger.id)"
            @click="deleteTrigger(trigger)"
          >
            {{ $t('agentTrigger.remove') }}
          </ButtonText>
        </template>
      </AgentConfigurationCard>
    </div>
    <Context
      v-if="!readOnly"
      ref="addTriggerContext"
      class="agent-configuration__add-context"
      max-height-if-outside-viewport
      @shown="$refs.addTriggerMenu.focus()"
    >
      <AgentGroupedAddMenu
        ref="addTriggerMenu"
        :items="triggerMenuItems"
        :search-placeholder="$t('agentTrigger.searchPlaceholder')"
        :empty-text="$t('agentTrigger.noResults')"
        @select="addTrigger($event.meta)"
        @close="$refs.addTriggerContext.hide()"
      />
    </Context>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentServiceForm from '@baserow_enterprise/components/agentApplication/AgentServiceForm'
import AgentGroupedAddMenu from '@baserow_enterprise/components/agentApplication/AgentGroupedAddMenu'
import AgentConfigurationCard from '@baserow_enterprise/components/agentApplication/AgentConfigurationCard'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { formatToolPayload } from '@baserow_enterprise/utils/agentChatEvents'
import {
  serviceFollowState,
  serviceFollowMethods,
} from '@baserow_enterprise/utils/agentServiceFollow'
import { AgentContextMixin } from '@baserow_enterprise/composables/useAgentContext'

export default {
  name: 'AgentTriggerSection',
  mixins: [AgentContextMixin],
  components: {
    AgentConfigurationCard,
    AgentGroupedAddMenu,
    AgentServiceForm,
    ReadOnlyForm,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      loading: false,
      addLoading: false,
      deletingIds: [],
      // Unsaved service values per trigger id, flushed by a per-trigger
      // debounced save.
      pendingServiceValues: {},
      ...serviceFollowState(),
    }
  },
  watch: {
    triggers: {
      handler(triggers) {
        triggers.forEach((trigger) => this.followService(trigger))
      },
      deep: true,
      immediate: true,
    },
  },
  computed: {
    canDeleteTrigger() {
      return this.hasAgentPermission(
        'agent_application.delete_trigger',
        this.application,
        this.application.workspace.id
      )
    },
    triggers() {
      return this.$store.getters[
        `${this.storePrefix}agentApplication/getTriggers`
      ]
    },
    triggerNodeTypes() {
      return this.$registry
        .getOrderedList('node')
        .filter(
          (nodeType) => nodeType.isTrigger && nodeType.getType() !== 'manual'
        )
    },
    triggerMenuItems() {
      const groups = new Map()
      this.triggerNodeTypes.forEach((nodeType) => {
        const group = nodeType.serviceType.group
        if (!groups.has(group.id)) {
          groups.set(group.id, { ...group, children: [] })
        }
        groups.get(group.id).children.push({
          id: `trigger-${nodeType.getType()}`,
          label: nodeType.name,
          value: nodeType.getType(),
          icon: nodeType.iconClass,
          iconColor: nodeType.iconColor,
          image: nodeType.image,
          description: nodeType.description,
          meta: nodeType,
        })
      })
      return Array.from(groups.values())
    },
  },
  created() {
    this.debouncedServiceSaves = {}
  },
  async mounted() {
    // The triggers themselves are fetched by the page; only the integrations
    // are needed here, because Local Baserow trigger forms pick a table
    // through the application's integrations in the store. Listing them is
    // a builder operation, so readers skip it.
    if (
      !this.hasAgentPermission(
        'application.list_integrations',
        this.application,
        this.application.workspace.id
      )
    ) {
      return
    }
    this.loading = true
    try {
      await this.$store.dispatch('integration/fetch', {
        application: this.application,
      })
    } catch (error) {
      notifyIf(error, 'application')
    } finally {
      this.loading = false
    }
  },
  beforeUnmount() {
    Object.values(this.debouncedServiceSaves).forEach((save) => save.flush())
  },
  methods: {
    triggerNodeType(trigger) {
      try {
        return this.$registry.get('node', trigger.service_type)
      } catch {
        return null
      }
    },
    triggerNodeTypeIcon(trigger) {
      return this.triggerNodeType(trigger)?.iconClass || 'iconoir-flash'
    },
    triggerNodeTypeName(trigger) {
      return this.triggerNodeType(trigger)?.name || trigger.service_type
    },
    formatPayload(payload) {
      return formatToolPayload(payload)
    },
    copyToken(trigger, token) {
      copyToClipboard(token.token)
      this.$refs[`copied-${trigger.id}-${token.token}`]?.[0]?.show()
    },
    async addTrigger(nodeType) {
      this.$refs.addTriggerContext.hide()
      this.addLoading = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/createTrigger`,
          {
            applicationId: this.application.id,
            values: { service_type: nodeType.getType() },
          }
        )
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.addLoading = false
      }
    },
    async onEnabledChange(trigger, enabled) {
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateTrigger`,
          {
            triggerId: trigger.id,
            values: { enabled },
          }
        )
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    async deleteTrigger(trigger) {
      if (this.deletingIds.includes(trigger.id)) {
        return
      }
      delete this.pendingServiceValues[trigger.id]
      delete this.debouncedServiceSaves[trigger.id]
      this.deletingIds = [...this.deletingIds, trigger.id]
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/deleteTrigger`,
          {
            triggerId: trigger.id,
          }
        )
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.deletingIds = this.deletingIds.filter((id) => id !== trigger.id)
      }
    },
    ...serviceFollowMethods({
      pendingFor(item) {
        return this.pendingServiceValues[item.id] || {}
      },
    }),
    onServiceValuesChanged(trigger, newValues) {
      this.formValues[trigger.id] = newValues
      if (this.readOnly) {
        return
      }
      const pending = this.pendingServiceValues[trigger.id] || {}
      const current = {
        ...(trigger.service || {}),
        ...pending,
      }
      const differences = Object.fromEntries(
        Object.entries(newValues).filter(
          ([key, value]) => !isEqual(value, current[key])
        )
      )
      if (Object.keys(differences).length === 0) {
        return
      }
      this.pendingServiceValues = {
        ...this.pendingServiceValues,
        [trigger.id]: { ...pending, ...differences },
      }
      if (!this.debouncedServiceSaves[trigger.id]) {
        this.debouncedServiceSaves[trigger.id] = debounce(
          () => this.saveServiceValues(trigger.id),
          1000
        )
      }
      this.debouncedServiceSaves[trigger.id]()
    },
    async saveServiceValues(triggerId) {
      const trigger = this.triggers.find((t) => t.id === triggerId)
      const pending = this.pendingServiceValues[triggerId]
      if (!trigger || !pending || Object.keys(pending).length === 0) {
        return
      }
      const service = {
        ...(trigger.service || {}),
        ...pending,
      }
      delete this.pendingServiceValues[triggerId]
      try {
        await this.$store.dispatch(
          `${this.storePrefix}agentApplication/updateTrigger`,
          {
            triggerId,
            values: { service },
          }
        )
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
