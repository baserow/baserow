<template>
  <article class="agent-action-card" :aria-busy="saving">
    <header class="agent-action-card__header">
      <button
        type="button"
        class="agent-action-card__toggle"
        :aria-expanded="expanded"
        @click="$emit('toggle')"
      >
        <Icon :icon="serviceType?.icon || 'iconoir-flash'" aria-hidden="true" />
        <span class="agent-action-card__title">{{
          action.name || serviceType?.name || action.type
        }}</span>
        <Icon
          :icon="
            expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
          aria-hidden="true"
        />
      </button>
      <Icon
        v-if="configurationErrors.length || saveError"
        icon="iconoir-warning-circle"
        type="error"
        :aria-label="saveError || $t('agent.actionMisconfigured')"
        role="img"
      />
      <span
        v-if="saving"
        class="agent-action-card__saving"
        role="status"
        :aria-label="$t('agent.saving')"
      />
      <SwitchInput
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
      <Alert
        v-if="configurationErrors.length"
        type="warning"
        class="margin-bottom-2"
      >
        <p>{{ $t('agent.actionMisconfigured') }}</p>
        <ul>
          <li v-for="error in configurationErrors" :key="error">{{ error }}</li>
        </ul>
      </Alert>
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
            :application="agent"
            :service="action.service"
            :service-type="serviceType"
            :default-values="action.service"
            :loading="saving"
            :allow-integration-editing="editable"
            @values-changed="onServiceValuesChanged"
          />
        </ReadOnlyForm>
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
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AgentFormulaInput from '@baserow/modules/agent/components/configuration/AgentFormulaInput'
import AgentActionInputs from '@baserow/modules/agent/components/configuration/AgentActionInputs'
import { serviceTypeOf } from '@baserow/modules/agent/utils/triggers'
import {
  ACTION_ERROR_LABELS,
  actionFieldLabel,
} from '@baserow/modules/agent/utils/actionLabels'

const props = defineProps({
  expanded: { type: Boolean, default: true },
  action: { type: Object, required: true },
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
const serviceType = computed(() => serviceTypeOf($registry, props.action.type))
provide('formulaComponent', AgentFormulaInput)
provide('dataProvidersAllowed', ['tool_input'])
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
const configurationErrors = computed(() =>
  Object.entries(props.action.errors || {}).map(([field, error]) =>
    t('agent.fieldError', {
      field: actionFieldLabel($registry, props.action.type, field, t),
      error: t(ACTION_ERROR_LABELS[error] || ACTION_ERROR_LABELS.invalid),
    })
  )
)
function update(values) {
  if (props.editable) emit('update', values)
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
