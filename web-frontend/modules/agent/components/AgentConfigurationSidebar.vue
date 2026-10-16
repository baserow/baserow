<template>
  <aside class="agent-configuration">
    <div class="agent-configuration__header">
      <button
        v-if="section"
        class="agent-configuration__icon-button"
        :aria-label="$t('action.back')"
        @click="section = null"
      >
        <i class="iconoir-nav-arrow-left" />
      </button>
      <h2>{{ $t(sectionTitle) }}</h2>
      <span class="agent-configuration__save-indicator">
        <span
          v-if="saving"
          class="agent-configuration__saving"
          role="status"
          :aria-label="$t('agent.saving')"
        />
      </span>
      <button
        class="agent-configuration__icon-button"
        :aria-label="$t('action.close')"
        @click="$emit('close')"
      >
        <i class="iconoir-cancel" />
      </button>
    </div>
    <div v-if="loading" class="agent-configuration__loading loading" />
    <div v-else-if="loadError" class="agent-configuration__body">
      <Alert type="error">
        {{ $t('agent.configurationLoadError') }}
        <template #actions
          ><Button type="secondary" size="small" @click="$emit('reload')">{{
            $t('action.retry')
          }}</Button></template
        >
      </Alert>
    </div>
    <template v-else>
      <div v-if="!section" class="agent-configuration__sections">
        <button
          class="agent-configuration__section"
          @click="section = 'instructions'"
        >
          <i class="agent-configuration__section-icon iconoir-page-edit" />
          <span class="agent-configuration__section-content"
            ><strong class="agent-configuration__section-title">{{
              $t('agent.instructions')
            }}</strong
            ><span
              class="agent-configuration__section-description"
              :title="$t('agent.instructionsDescription')"
              >{{ $t('agent.instructionsDescription') }}</span
            ></span
          >
          <i
            class="agent-configuration__section-caret"
            :class="
              errors.instructions
                ? 'iconoir-warning-circle'
                : 'iconoir-nav-arrow-right'
            "
          />
        </button>
        <button
          class="agent-configuration__section"
          @click="section = 'settings'"
        >
          <i class="agent-configuration__section-icon iconoir-settings" />
          <span class="agent-configuration__section-content"
            ><strong class="agent-configuration__section-title">{{
              $t('agent.agentSettings')
            }}</strong
            ><span
              class="agent-configuration__section-description"
              :title="$t('agent.agentSettingsDescription')"
              >{{ $t('agent.agentSettingsDescription') }}</span
            ></span
          >
          <i
            class="agent-configuration__section-caret"
            :class="
              errors.name || errors.provider_type || errors.model_identifier
                ? 'iconoir-warning-circle'
                : 'iconoir-nav-arrow-right'
            "
          />
        </button>
      </div>
      <ReadOnlyForm
        v-else
        :read-only="!editable"
        class="agent-configuration__form"
      >
        <form class="agent-configuration__body" @submit.prevent>
          <FormGroup
            v-if="section === 'instructions'"
            :label="$t('agent.instructions')"
            :error="Boolean(errors.instructions)"
            :error-message="errorMessage('instructions')"
            :helper-text="$t('agent.instructionsHelper')"
            small-label
            required
          >
            <FormTextarea
              ref="instructionsInput"
              :model-value="configuration.instructions || ''"
              :error="Boolean(errors.instructions)"
              :disabled="!editable"
              :rows="10"
              :maxlength="100000"
              @update:model-value="$emit('change', { instructions: $event })"
              @blur="$emit('flush')"
            />
          </FormGroup>
          <template v-else>
            <FormGroup
              :label="$t('agent.name')"
              :error="Boolean(errors.name)"
              :error-message="errorMessage('name')"
              small-label
              required
            >
              <FormInput
                ref="nameInput"
                :model-value="configuration.name"
                :error="Boolean(errors.name)"
                :disabled="!editable"
                :maxlength="160"
                @update:model-value="$emit('change', { name: $event })"
                @blur="$emit('flush')"
              />
            </FormGroup>
            <FormGroup
              class="margin-top-2"
              :label="$t('agent.provider')"
              :error="Boolean(errors.provider_type)"
              :error-message="errorMessage('provider_type')"
              small-label
              required
            >
              <Dropdown
                ref="providerInput"
                :model-value="configuration.provider_type"
                :error="Boolean(errors.provider_type)"
                :disabled="!editable || availabilityLoading"
                :placeholder="$t('action.makeChoice')"
                :show-search="false"
                fixed-items
                @update:model-value="changeProvider"
              >
                <DropdownItem
                  v-for="provider in providers"
                  :key="provider.type"
                  :value="provider.type"
                  :name="provider.name"
                  :disabled="!enabledModels[provider.type]?.length"
                />
              </Dropdown>
            </FormGroup>
            <FormGroup
              class="margin-top-2"
              :label="$t('agent.model')"
              :error="Boolean(errors.model_identifier)"
              :error-message="errorMessage('model_identifier')"
              small-label
              required
            >
              <Dropdown
                ref="modelInput"
                :model-value="configuration.model_identifier"
                :error="Boolean(errors.model_identifier)"
                :disabled="
                  !editable ||
                  availabilityLoading ||
                  !configuration.provider_type
                "
                :placeholder="$t('action.makeChoice')"
                fixed-items
                @update:model-value="
                  $emit('change', { model_identifier: $event })
                "
              >
                <DropdownItem
                  v-for="model in models"
                  :key="model"
                  :value="model"
                  :name="model"
                  :disabled="!availableModels.includes(model)"
                />
              </Dropdown>
            </FormGroup>
          </template>
        </form>
      </ReadOnlyForm>
      <div
        v-if="saveError"
        class="agent-configuration__save-status"
        aria-live="polite"
      >
        <span>{{ $t('agent.configurationSaveError') }}</span>
        <Button type="secondary" size="small" @click="$emit('flush')">{{
          $t('action.retry')
        }}</Button>
      </div>
    </template>
  </aside>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'

const props = defineProps({
  configuration: { type: Object, required: true },
  errors: { type: Object, required: true },
  enabledModels: { type: Object, required: true },
  editable: Boolean,
  loading: Boolean,
  loadError: Boolean,
  availabilityLoading: Boolean,
  saving: Boolean,
  saveError: Boolean,
})
const emit = defineEmits(['close', 'change', 'flush', 'reload'])
const { $registry, $i18n } = useNuxtApp()
const section = ref(null)
const nameInput = ref(null)
const instructionsInput = ref(null)
const providerInput = ref(null)
const modelInput = ref(null)
const sectionTitle = computed(() =>
  section.value === 'instructions'
    ? 'agent.instructions'
    : section.value === 'settings'
      ? 'agent.agentSettings'
      : 'agent.configuration'
)
const providers = computed(() => {
  const types = Object.keys(props.enabledModels).filter(
    (type) => props.enabledModels[type].length > 0
  )
  if (props.configuration.provider_type)
    types.push(props.configuration.provider_type)
  const registryTypes = $registry.getAll('generativeAIModel')
  return [...new Set(types)].map((type) => ({
    type,
    name: registryTypes[type]?.getName() || type,
  }))
})
const availableModels = computed(
  () => props.enabledModels[props.configuration.provider_type] || []
)
const models = computed(() =>
  [
    ...new Set([
      ...availableModels.value,
      props.configuration.model_identifier,
    ]),
  ].filter(Boolean)
)
const errorMessage = (field) => {
  if (!props.errors[field]) return ''
  return $i18n.t(
    props.errors[field] === 'unavailable'
      ? 'agent.modelUnavailable'
      : 'error.requiredField'
  )
}
const changeProvider = (providerType) =>
  emit('change', { provider_type: providerType, model_identifier: null })
async function focusField(field) {
  section.value = field === 'instructions' ? 'instructions' : 'settings'
  await nextTick()
  const input = {
    name: nameInput,
    instructions: instructionsInput,
    provider_type: providerInput,
    model_identifier: modelInput,
  }[field]?.value
  if (input?.focus) input.focus()
  else input?.$el?.focus()
}
defineExpose({ focusField })
</script>
