<template>
  <div>
    <div
      v-if="triggers.length === 0"
      class="agent-configuration__placeholder"
      :class="{ 'margin-bottom-2': !readOnly }"
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
    <div v-if="triggers.length > 0" class="agent-configuration__card-list">
      <div
        v-for="trigger in triggers"
        :key="trigger.id"
        class="agent-configuration__card"
      >
        <div class="agent-configuration__card-header">
          <a
            class="agent-configuration__card-summary"
            @click="toggleExpanded(trigger.id)"
          >
            <i
              class="agent-configuration__card-chevron iconoir-nav-arrow-right"
              :class="{
                'agent-configuration__card-chevron--expanded': isExpanded(
                  trigger.id
                ),
              }"
            ></i>
            <i
              class="agent-configuration__card-icon"
              :class="triggerNodeTypeIcon(trigger)"
            ></i>
            <div class="agent-configuration__card-name">
              {{ triggerNodeTypeName(trigger) }}
            </div>
          </a>
          <SwitchInput
            small
            :value="trigger.enabled"
            :disabled="readOnly"
            :title="$t('agentTrigger.enabledLabel')"
            @input="onEnabledChange(trigger, $event)"
          ></SwitchInput>
          <ButtonIcon
            v-if="!readOnly"
            icon="iconoir-bin"
            :title="$t('agentTrigger.remove')"
            @click="deleteTrigger(trigger)"
          ></ButtonIcon>
        </div>
        <div
          v-if="isExpanded(trigger.id)"
          class="agent-configuration__card-body"
        >
          <ReadOnlyForm :read-only="readOnly">
            <AgentServiceForm
              v-if="triggerNodeType(trigger)"
              :key="`${trigger.id}-${trigger.service_type}`"
              :application="application"
              :service-type="triggerNodeType(trigger).serviceType"
              :service="trigger.service || {}"
              @values-changed="onServiceValuesChanged(trigger, $event)"
            />
          </ReadOnlyForm>
        </div>
      </div>
    </div>
    <template v-if="!readOnly">
      <Button
        type="secondary"
        icon="iconoir-plus"
        :loading="addLoading"
        :disabled="loading"
        @click="
          $refs.addTriggerContext.toggle(
            $event.currentTarget,
            'bottom',
            'left',
            4
          )
        "
      >
        {{ $t('agentTrigger.addTrigger') }}
      </Button>
      <Context
        ref="addTriggerContext"
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
    </template>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import isEqual from 'lodash/isEqual'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentServiceForm from '@baserow_enterprise/components/agentApplication/AgentServiceForm'
import AgentGroupedAddMenu from '@baserow_enterprise/components/agentApplication/AgentGroupedAddMenu'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'AgentTriggerSection',
  components: { AgentGroupedAddMenu, AgentServiceForm, ReadOnlyForm },
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
      // Newly added triggers start expanded; existing ones start collapsed so
      // that multiple triggers stay scannable.
      expandedTriggerIds: [],
      // Unsaved service values per trigger id, flushed by a per-trigger
      // debounced save.
      pendingServiceValues: {},
    }
  },
  computed: {
    triggers() {
      return this.$store.getters['agentApplication/getTriggers']
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
    // through the application's integrations in the store.
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
    isExpanded(triggerId) {
      return this.expandedTriggerIds.includes(triggerId)
    },
    toggleExpanded(triggerId) {
      if (this.isExpanded(triggerId)) {
        this.expandedTriggerIds = this.expandedTriggerIds.filter(
          (id) => id !== triggerId
        )
      } else {
        this.expandedTriggerIds.push(triggerId)
      }
    },
    async addTrigger(nodeType) {
      this.$refs.addTriggerContext.hide()
      this.addLoading = true
      try {
        const trigger = await this.$store.dispatch(
          'agentApplication/createTrigger',
          {
            applicationId: this.application.id,
            values: { service_type: nodeType.getType() },
          }
        )
        this.expandedTriggerIds.push(trigger.id)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.addLoading = false
      }
    },
    async onEnabledChange(trigger, enabled) {
      try {
        await this.$store.dispatch('agentApplication/updateTrigger', {
          triggerId: trigger.id,
          values: { enabled },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    async deleteTrigger(trigger) {
      delete this.pendingServiceValues[trigger.id]
      delete this.debouncedServiceSaves[trigger.id]
      try {
        await this.$store.dispatch('agentApplication/deleteTrigger', {
          triggerId: trigger.id,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
    onServiceValuesChanged(trigger, newValues) {
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
        await this.$store.dispatch('agentApplication/updateTrigger', {
          triggerId,
          values: { service },
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
