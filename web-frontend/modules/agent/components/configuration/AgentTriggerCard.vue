<template>
  <article class="agent-trigger-card" :aria-busy="saving">
    <header class="agent-trigger-card__header">
      <div class="agent-trigger-card__title">
        <span
          v-tooltip="typeName"
          class="agent-trigger-card__type"
          role="img"
          :aria-label="typeName"
        >
          <Icon
            :icon="serviceType?.icon || 'iconoir-flash'"
            class="agent-trigger-card__icon"
            aria-hidden="true"
          />
        </span>
        <div class="agent-trigger-card__name" @click="startRename">
          <Editable
            ref="nameEditable"
            class="agent-trigger-card__name-text"
            :value="shownName"
            @editing="renaming = $event"
            @change="rename"
          />
        </div>
        <button
          v-if="editable && !renaming"
          type="button"
          class="agent-trigger-card__rename"
          :aria-label="$t('agent.renameTrigger')"
          @click="startRename"
        >
          <i class="iconoir-edit-pencil" aria-hidden="true" />
        </button>
        <Icon
          v-if="configurationError"
          v-tooltip="configurationError"
          class="agent-trigger-card__status"
          icon="iconoir-warning-circle"
          type="error"
          size="small"
          role="img"
          :aria-label="configurationError"
        />
      </div>
      <span
        v-if="saving"
        class="agent-trigger-card__saving"
        role="status"
        :aria-label="$t('agent.saving')"
      />
      <SwitchInput
        class="agent-trigger-card__switch"
        small
        role="switch"
        :tabindex="editable ? 0 : -1"
        :aria-label="$t('agent.triggerEnabled')"
        :aria-checked="trigger.enabled"
        :aria-disabled="!editable"
        :model-value="trigger.enabled"
        :disabled="!editable"
        @update:model-value="$emit('update', { enabled: $event })"
        @keydown.enter.prevent="toggleEnabled"
        @keydown.space.prevent="toggleEnabled"
      />
    </header>
    <div v-if="serviceType" class="agent-trigger-card__body">
      <div
        class="agent-trigger-card__section agent-trigger-card__configuration"
      >
        <div class="agent-trigger-card__service">
          <component
            :is="serviceType.formComponent"
            ref="form"
            :key="`${trigger.type}-${serviceReverts}`"
            :application="agent"
            :service="trigger.service"
            :service-type="serviceType"
            :default-values="trigger.service"
            :loading="saving"
            @values-changed="onServiceValuesChanged"
          />
        </div>
        <p v-if="serviceError" class="agent-trigger-card__error" role="alert">
          {{ serviceError }}
        </p>
      </div>
      <div class="agent-trigger-card__section">
        <FormGroup
          class="agent-trigger-card__message"
          :label="$t('agent.triggerMessage')"
          :help-icon-tooltip="$t('agent.triggerMessageHelper')"
          small-label
        >
          <AgentTriggerMessageInput
            :model-value="trigger.message"
            :disabled="!editable"
            :placeholder="$t('agent.triggerMessagePlaceholder')"
            @update:model-value="$emit('update', { message: $event })"
          />
        </FormGroup>
        <Expandable
          v-if="schemaProperties.length"
          class="agent-trigger-card__schema"
        >
          <template #header="{ expanded, toggle }">
            <button
              type="button"
              class="agent-trigger-card__schema-toggle"
              :aria-expanded="expanded"
              @click="toggle"
            >
              <span class="agent-trigger-card__schema-title">
                {{ $t('agent.triggerDataProvides') }}
              </span>
              <span class="agent-trigger-card__schema-count">
                {{
                  $t('agent.triggerDataValues', {
                    count: schemaProperties.length,
                  })
                }}
              </span>
              <i
                class="agent-trigger-card__schema-chevron"
                :class="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                aria-hidden="true"
              ></i>
            </button>
          </template>
          <ul class="agent-trigger-card__schema-list">
            <li v-for="property in schemaProperties" :key="property.key">
              <span>{{ property.title }}</span>
              <span class="agent-trigger-card__schema-type">{{
                property.type
              }}</span>
            </li>
          </ul>
        </Expandable>
      </div>
    </div>
    <footer v-if="editable" class="agent-trigger-card__footer">
      <ButtonText
        type="secondary"
        size="small"
        button-type="button"
        icon="iconoir-bin"
        class="agent-trigger-card__delete"
        @click="$emit('delete')"
      >
        {{ $t('agent.deleteTrigger') }}
      </ButtonText>
    </footer>
  </article>
</template>

<script setup>
import { computed, inject, nextTick, provide, reactive, ref, toRef } from 'vue'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import Icon from '@baserow/modules/core/components/Icon'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import Editable from '@baserow/modules/core/components/Editable'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import AgentTriggerMessageInput from '@baserow/modules/agent/components/configuration/AgentTriggerMessageInput'
import { serviceTypeOf } from '@baserow/modules/agent/utils/triggers'
import { TRIGGER_NAME_MAX_LENGTH } from '@baserow/modules/agent/constants'

const props = defineProps({
  /** The trigger as the card shows it, edits included. */
  trigger: { type: Object, required: true },
  /** The Agent's workspace, for the hosted service form. */
  workspace: { type: Object, default: null },
  /** Whether the user may change the trigger. */
  editable: Boolean,
  /** Whether a save of the trigger is in flight. */
  saving: Boolean,
  /** Why the server rejected the service values, or ''. */
  serviceError: { type: String, default: '' },
  /** How often a failed save reverted the service values the form shows. */
  serviceReverts: { type: Number, default: 0 },
})
const emit = defineEmits(['update', 'delete'])
const { $registry } = useNuxtApp()
const { t } = useI18n()
const agent = inject('agentApplication')
const form = ref(null)
const nameEditable = ref(null)
const renaming = ref(false)
const serviceType = computed(() => serviceTypeOf($registry, props.trigger.type))
// Hosted service forms inject these like in Automation's node side panel.
provide('formulaComponent', FormulaInputField)
provide('dataProvidersAllowed', [])
provide('workspace', toRef(props, 'workspace'))
provide(
  'applicationContext',
  reactive({
    get agent() {
      return agent.value
    },
    get trigger() {
      return props.trigger
    },
  })
)
const typeName = computed(() => serviceType.value?.name || props.trigger.type)
const defaultName = computed(
  () =>
    serviceType.value?.getDefaultName(props.trigger.service) ||
    props.trigger.type
)
const shownName = computed(() => props.trigger.name || defaultName.value)
const configurationError = computed(
  () =>
    serviceType.value?.getErrorMessage({
      service: props.trigger.service,
      workspace: props.workspace,
    }) || ''
)
const schemaProperties = computed(() => {
  const schema = $registry
    .get('agentDataProvider', 'trigger')
    .getDataSchema({ trigger: props.trigger })
  return Object.entries(schema?.properties || {}).map(([key, property]) => ({
    key,
    title: property.title || key,
    type: property.type,
  }))
})

function onServiceValuesChanged(values) {
  if (!props.editable) return
  if (form.value?.isFormValid && !form.value.isFormValid()) return
  emit('update', { service: values })
}

function startRename() {
  if (props.editable && !renaming.value) nameEditable.value.edit()
}

/**
 * Saves the typed name; a blank one, or the default, clears the name so the
 * default follows the trigger's settings.
 *
 * @param {object} event The Editable's change, with the typed `value`.
 */
function rename({ value }) {
  const typed = Array.from(value.trim())
    .slice(0, TRIGGER_NAME_MAX_LENGTH)
    .join('')
  emit('update', { name: typed === defaultName.value ? '' : typed })
  // An unchanged shown name, like a cleared default, doesn't reset the edited text.
  nextTick(() => nameEditable.value?.set())
}

function toggleEnabled() {
  if (props.editable) emit('update', { enabled: !props.trigger.enabled })
}
</script>
