<template>
  <article class="agent-action-card" :aria-busy="saving">
    <header class="agent-action-card__header">
      <button
        type="button"
        class="agent-action-card__toggle"
        :aria-expanded="expanded"
        @click="$emit('toggle')"
      >
        <Icon
          :icon="
            expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
          aria-hidden="true"
        />
        <Icon :icon="serviceType?.icon || 'iconoir-flash'" aria-hidden="true" />
        <span class="agent-action-card__title">{{
          action.name || serviceType?.name || action.type
        }}</span>
      </button>
      <button
        v-if="lockedModal"
        v-tooltip="lockedReason"
        type="button"
        class="agent-action-card__lock"
        :aria-label="lockedReason"
        @click="showLockedModal"
      >
        <i class="iconoir-lock" aria-hidden="true" />
      </button>
      <template v-else-if="configurationErrors.length">
        <button
          type="button"
          class="agent-action-card__misconfigured"
          aria-haspopup="dialog"
          :aria-label="$t('agent.actionMisconfigured')"
          @click="
            misconfiguredContext.toggle($event.currentTarget, 'bottom', 'right')
          "
        >
          <Icon icon="iconoir-warning-circle" type="error" aria-hidden="true" />
        </button>
        <Context
          ref="misconfiguredContext"
          class="agent-action-card__misconfigured-context"
          role="dialog"
          :aria-label="$t('agent.actionMisconfigured')"
        >
          <p class="agent-action-card__misconfigured-text">
            {{ $t('agent.actionMisconfigured') }}
          </p>
          <ul class="agent-action-card__misconfigured-list">
            <li v-for="error in configurationErrors" :key="error">
              {{ error }}
            </li>
          </ul>
        </Context>
      </template>
      <Icon
        v-else-if="saveError"
        icon="iconoir-warning-circle"
        type="error"
        :aria-label="saveError"
        role="img"
      />
      <span class="agent-action-card__saving-slot">
        <span
          v-if="saving"
          class="agent-action-card__saving"
          role="status"
          :aria-label="$t('agent.saving')"
        />
      </span>
      <SwitchInput
        v-tooltip="enabledTooltip"
        :class="{ 'agent-action-card__switch--locked': locked }"
        small
        role="switch"
        :tabindex="editable ? 0 : -1"
        :aria-label="$t('agent.actionEnabled', { name: action.name })"
        :aria-checked="action.enabled"
        :aria-disabled="!editable"
        :model-value="action.enabled"
        :disabled="!editable"
        @update:model-value="update({ enabled: $event })"
        @keydown.enter.prevent="update({ enabled: !action.enabled })"
        @keydown.space.prevent="update({ enabled: !action.enabled })"
      />
    </header>
    <div v-show="expanded" class="agent-action-card__body">
      <FormGroup
        :label="$t('agent.actionName')"
        :help-icon-tooltip="$t('agent.actionNameHelp')"
        class="margin-bottom-2"
        small-label
        required
      >
        <FormInput
          :model-value="action.name"
          :disabled="!editable"
          :maxlength="64"
          @update:model-value="update({ name: $event })"
        />
      </FormGroup>
      <div
        class="agent-action-card__settings"
        :class="{
          'agent-action-card__settings--locked': locked,
          'agent-action-card__settings--upgradable': lockedModal,
        }"
        @click="showLockedModal"
      >
        <div :inert="locked || null">
          <FormGroup
            :label="$t('agent.actionDescription')"
            :help-icon-tooltip="$t('agent.actionDescriptionHelp')"
            class="margin-bottom-2"
            small-label
          >
            <FormTextarea
              :model-value="action.description"
              :maxlength="10000"
              :disabled="!editable"
              :rows="3"
              @update:model-value="update({ description: $event })"
            />
          </FormGroup>
          <FormGroup
            class="agent-action-card__approval"
            :helper-text="$t('agent.actionAskFirstHelp')"
          >
            <SwitchInput
              small
              role="switch"
              :tabindex="editable ? 0 : -1"
              :aria-checked="action.ask_first"
              :aria-disabled="!editable"
              :model-value="action.ask_first"
              :disabled="!editable"
              @update:model-value="update({ ask_first: $event })"
              @keydown.enter.prevent="update({ ask_first: !action.ask_first })"
              @keydown.space.prevent="update({ ask_first: !action.ask_first })"
            >
              {{ $t('agent.actionAskFirst') }}
            </SwitchInput>
          </FormGroup>
          <AgentActionInputs
            :model-value="action.inputs"
            :editable="editable"
            @update:model-value="update({ inputs: $event })"
          />
          <div v-if="serviceType" class="agent-action-card__service">
            <h4>{{ $t('agent.actionConfiguration') }}</h4>
            <ReadOnlyForm :read-only="!editable" :inert="!editable">
              <component
                :is="serviceType.formComponent"
                ref="form"
                small
                :application="agent"
                :service="action.service"
                :service-type="serviceType"
                :default-values="action.service"
                :loading="saving"
                :allow-integration-editing="editable"
                v-bind="hostedFormProps"
                @values-changed="onServiceValuesChanged"
              />
            </ReadOnlyForm>
          </div>
        </div>
      </div>
      <p v-if="saveError" class="agent-action-card__error" role="alert">
        {{ saveError }}
      </p>
      <ButtonText
        v-if="saveError && editable"
        type="secondary"
        button-type="button"
        @click="$emit('retry')"
        >{{ $t('action.retry') }}</ButtonText
      >
    </div>
    <footer v-if="editable" v-show="expanded" class="agent-action-card__footer">
      <ButtonText
        type="secondary"
        size="small"
        button-type="button"
        icon="iconoir-bin"
        @click="$emit('delete')"
        >{{ $t('agent.deleteAction') }}</ButtonText
      >
    </footer>
    <component
      :is="lockedModal[0]"
      v-if="lockedModal"
      ref="lockedModalRef"
      :workspace="workspace"
      v-bind="lockedModal[1]"
    />
  </article>
</template>

<script setup>
import {
  computed,
  inject,
  nextTick,
  provide,
  reactive,
  ref,
  toRef,
  watch,
} from 'vue'
import isEqual from 'lodash/isEqual'
import { useNuxtApp } from '#app'
import { useI18n } from 'vue-i18n'
import Icon from '@baserow/modules/core/components/Icon'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import Context from '@baserow/modules/core/components/Context'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentFormulaInput from '@baserow/modules/agent/components/configuration/AgentFormulaInput'
import AgentActionInputs from '@baserow/modules/agent/components/configuration/AgentActionInputs'
import { provideWorkspaceAccessLink } from '@baserow/modules/agent/composables/useWorkspaceAccessLink'
import { serviceTypeOf } from '@baserow/modules/agent/utils/triggers'
import {
  ACTION_ERROR_LABELS,
  actionFieldLabel,
} from '@baserow/modules/agent/utils/actionLabels'

const props = defineProps({
  expanded: { type: Boolean, default: true },
  action: { type: Object, required: true },
  /** What the run identity offers this action's type, or null while it loads. */
  typeOptions: { type: Object, default: null },
  /** Whether the Agent acts as a workspace identity that is available. */
  runAsActive: Boolean,
  workspace: { type: Object, default: null },
  editable: Boolean,
  saving: Boolean,
  saveError: { type: String, default: '' },
})
const emit = defineEmits(['update', 'delete', 'retry', 'toggle'])
const { $registry } = useNuxtApp()
const { t } = useI18n()
const agent = inject('agentApplication')
const form = ref(null)
const misconfiguredContext = ref(null)
const serviceType = computed(() => serviceTypeOf($registry, props.action.type))
provide('formulaComponent', AgentFormulaInput)
provideWorkspaceAccessLink()
provide('dataProvidersAllowed', ['tool_input'])
// Filters are resolved when the call is sent, without its inputs.
provide('filterDataProvidersAllowed', [])
provide('workspace', toRef(props, 'workspace'))
provide(
  'applicationContext',
  reactive({
    get agent() {
      return agent.value
    },
    get action() {
      return props.action
    },
  })
)
const formChoices = computed(() => props.typeOptions?.form_choices ?? null)
/**
 * A type that acts as the run identity chooses from what the identity can read,
 * which is nothing without one. Passed only then, so other forms get no attribute.
 */
const hostedFormProps = computed(() => {
  if (!formChoices.value) return {}
  return {
    ...formChoices.value,
    ...(props.runAsActive
      ? {}
      : { formChoicesError: t('agent.noWorkspaceAccessTables') }),
  }
})
const configurationErrors = computed(() =>
  Object.entries(props.action.errors || {}).map(([field, error]) =>
    t('agent.fieldError', {
      field: actionFieldLabel($registry, props.action.type, field, t),
      error: t(ACTION_ERROR_LABELS[error] || ACTION_ERROR_LABELS.invalid),
    })
  )
)
/** Why the action's type can't be used in the workspace, or ''. */
const lockedReason = computed(
  () =>
    serviceType.value?.isDeactivatedReason({ workspace: props.workspace }) || ''
)
const locked = computed(() => Boolean(lockedReason.value))
/** The upgrade modal, only when a license would unlock the type. */
const lockedModal = computed(() =>
  locked.value
    ? serviceType.value.getDeactivatedClickModal({ workspace: props.workspace })
    : null
)
const lockedModalRef = ref(null)
function showLockedModal() {
  lockedModalRef.value?.show()
}
const enabledTooltip = computed(() => {
  if (locked.value)
    return t('agent.actionLockedTooltip', { reason: lockedReason.value })
  if (!props.editable) return null
  return t(
    props.action.enabled
      ? 'agent.actionEnabledTooltip'
      : 'agent.actionDisabledTooltip'
  )
})
// The backend refuses any other change while the type is locked.
const LOCKED_EDITABLE_FIELDS = ['name', 'enabled']
function update(values) {
  if (!props.editable) return
  if (
    locked.value &&
    Object.keys(values).some((field) => !LOCKED_EDITABLE_FIELDS.includes(field))
  )
    return
  emit('update', values)
}
// Shared service forms expose reset() to adopt a remote configuration update.
watch(
  () => props.action.service,
  async () => {
    await nextTick()
    await form.value?.reset?.()
  }
)
function onServiceValuesChanged(values) {
  if (
    Object.entries(values).every(([field, value]) =>
      isEqual(value, props.action.service[field])
    )
  )
    return
  if (form.value?.isFormValid && !form.value.isFormValid()) return
  update({ service: values })
}
</script>
