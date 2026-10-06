<template>
  <div>
    <FormGroup
      small-label
      :label="$t('agentSettings.nameLabel')"
      class="margin-bottom-2"
    >
      <FormInput
        v-model="name"
        :disabled="readOnly"
        @input="onNameInput"
      ></FormInput>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('agentSettings.providerLabel')"
      class="margin-bottom-2"
    >
      <Dropdown
        :model-value="agent?.ai_generative_ai_type || null"
        :show-search="false"
        :fixed-items="true"
        :disabled="readOnly"
        @update:model-value="onTypeChange"
      >
        <DropdownItem
          v-for="aiType in aiTypes"
          :key="aiType.getType()"
          :name="aiType.getName()"
          :value="aiType.getType()"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('agentSettings.modelLabel')"
      class="margin-bottom-1"
    >
      <Dropdown
        :model-value="agent?.ai_generative_ai_model || null"
        :show-search="false"
        :fixed-items="true"
        :disabled="readOnly || !agent?.ai_generative_ai_type"
        @update:model-value="onModelChange"
      >
        <DropdownItem
          v-for="model in modelsForType"
          :key="model"
          :name="model"
          :value="model"
        />
      </Dropdown>
    </FormGroup>
    <div class="agent-configuration__hint margin-bottom-3">
      {{ $t('agentSettings.modelHint') }}
    </div>
    <FormGroup
      small-label
      :label="$t('agentSettings.styleLabel')"
      class="margin-bottom-1"
    >
      <SegmentControl
        :segments="styleSegments"
        :active-index="styleIndex"
        :disabled="readOnly"
        @update:active-index="onStyleChange"
      ></SegmentControl>
    </FormGroup>
    <div class="agent-configuration__hint margin-bottom-3">
      {{ $t(`agentSettings.style_${style}Hint`) }}
    </div>
    <div v-if="canDuplicate || canDelete" class="agent-configuration__rows">
      <AgentConfigurationSectionRow
        v-if="canDuplicate"
        icon="iconoir-copy"
        :title="$t('agentSettings.duplicate')"
        :summary="$t('agentSettings.duplicateDescription')"
        :right-label="duplicating ? $t('agentSettings.duplicating') : ''"
        @click="duplicate"
      />
      <AgentConfigurationSectionRow
        v-if="canDelete"
        icon="iconoir-bin"
        :title="$t('agentSettings.delete')"
        :summary="$t('agentSettings.deleteDescription')"
        @click="$refs.deleteModal.show()"
      />
    </div>
    <Modal v-if="canDelete" ref="deleteModal" small>
      <div>
        <h2 class="box__title">{{ $t('agentSettings.deleteTitle') }}</h2>
        <p>{{ $t('agentSettings.deleteText', { name: application.name }) }}</p>
        <div class="actions actions--right actions--gap margin-bottom-0">
          <Button type="secondary" @click="$refs.deleteModal.hide()">
            {{ $t('agentSettings.cancel') }}
          </Button>
          <Button type="danger" :loading="deleting" @click="deleteAgent">
            {{ $t('agentSettings.delete') }}
          </Button>
        </div>
      </div>
    </Modal>
  </div>
</template>

<script>
import { defineComponent, ref, computed } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useI18n } from '#imports'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'
import ApplicationService from '@baserow/modules/core/services/application'
import AgentConfigurationSectionRow from '@baserow_enterprise/components/agentApplication/AgentConfigurationSectionRow'
import { useSeededAgentField } from '@baserow_enterprise/composables/useSeededAgentField'
import {
  STYLE_TEMPERATURES,
  snapStyle,
} from '@baserow_enterprise/utils/agentSettings'
import { useAgentContext } from '@baserow_enterprise/composables/useAgentContext'

const STYLES = ['precise', 'balanced', 'creative']

export default defineComponent({
  name: 'AgentAgentSettingsSection',
  components: { AgentConfigurationSectionRow },
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
  setup(props) {
    const store = useStore()
    const { storePrefix, hasPermission } = useAgentContext()
    const { $registry, $client } = useNuxtApp()
    const { t } = useI18n()
    const canUpdate = computed(() => !props.readOnly)
    const {
      agent,
      value: name,
      onInput: onNameInput,
    } = useSeededAgentField('name', { canUpdate })

    const workspace = computed(() =>
      store.getters['workspace/get'](props.application.workspace.id)
    )
    const enabledModels = computed(() =>
      getEnabledModelsForAIProviderFeature(workspace.value, 'agent_builder')
    )
    // The configured provider and model are listed even when the workspace
    // no longer enables them (or isn't loaded, as in a template preview), so
    // the dropdowns always show what the agent actually uses.
    const aiTypes = computed(() => {
      const types = Object.keys(enabledModels.value)
      const current = agent.value?.ai_generative_ai_type
      if (current && !types.includes(current)) {
        types.push(current)
      }
      return types
        .map((type) => {
          try {
            return $registry.get('generativeAIModel', type)
          } catch {
            return null
          }
        })
        .filter((aiType) => aiType !== null)
    })
    const modelsForType = computed(() => {
      const models = [
        ...(enabledModels.value[agent.value?.ai_generative_ai_type] || []),
      ]
      const current = agent.value?.ai_generative_ai_model
      if (current && !models.includes(current)) {
        models.unshift(current)
      }
      return models
    })

    const saveModel = async (values) => {
      if (!agent.value || props.readOnly) {
        return
      }
      try {
        await store.dispatch(`${storePrefix}agentApplication/update`, {
          agentId: agent.value.id,
          values,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }
    const onTypeChange = (type) => {
      if (type === agent.value?.ai_generative_ai_type) {
        return
      }
      saveModel({
        ai_generative_ai_type: type,
        ai_generative_ai_model: enabledModels.value[type]?.[0] || null,
      })
    }
    const onModelChange = (model) => {
      if (model !== agent.value?.ai_generative_ai_model) {
        saveModel({ ai_generative_ai_model: model })
      }
    }

    const style = computed(() => snapStyle(agent.value?.ai_temperature))
    const styleIndex = computed(() => STYLES.indexOf(style.value))
    const styleSegments = computed(() =>
      STYLES.map((item) => ({ label: t(`agentSettings.style_${item}`) }))
    )
    const onStyleChange = (index) => {
      const selected = STYLES[index]
      if (selected !== style.value) {
        saveModel({ ai_temperature: STYLE_TEMPERATURES[selected] })
      }
    }

    const canDuplicate = computed(() =>
      hasPermission(
        'application.duplicate',
        props.application,
        props.application.workspace.id
      )
    )
    const canDelete = computed(() =>
      hasPermission(
        'application.delete',
        props.application,
        props.application.workspace.id
      )
    )
    const duplicating = ref(false)
    const duplicate = async () => {
      if (duplicating.value) {
        return
      }
      duplicating.value = true
      try {
        const { data: job } = await ApplicationService($client).asyncDuplicate(
          props.application.id
        )
        await store.dispatch('job/create', job)
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        duplicating.value = false
      }
    }
    const deleting = ref(false)
    const deleteAgent = async () => {
      if (deleting.value) {
        return
      }
      deleting.value = true
      try {
        await store.dispatch('application/delete', props.application)
        await store.dispatch('toast/restore', {
          trash_item_type: 'application',
          trash_item_id: props.application.id,
        })
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        deleting.value = false
      }
    }

    return {
      agent,
      name,
      onNameInput,
      aiTypes,
      modelsForType,
      onTypeChange,
      onModelChange,
      style,
      styleIndex,
      styleSegments,
      onStyleChange,
      canDuplicate,
      canDelete,
      duplicating,
      duplicate,
      deleting,
      deleteAgent,
    }
  },
})
</script>
