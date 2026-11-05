<template>
  <aside class="agent-configuration" :aria-busy="loading">
    <div
      class="agent-configuration__header"
      :class="{ 'agent-configuration__header--section': selectedSection }"
    >
      <ButtonText
        v-if="selectedSection"
        class="agent-configuration__header-button"
        type="secondary"
        button-type="button"
        icon="iconoir-nav-arrow-left"
        :aria-label="$t('action.back')"
        @click="section = null"
      />
      <h2>{{ selectedSection?.name || $t('agent.configuration') }}</h2>
      <span class="agent-configuration__save-indicator">
        <span
          v-if="saving"
          class="agent-configuration__saving"
          role="status"
          :aria-label="$t('agent.saving')"
        />
      </span>
      <ButtonText
        class="agent-configuration__header-button"
        type="secondary"
        button-type="button"
        icon="iconoir-cancel"
        :aria-label="$t('action.close')"
        @click="$emit('close')"
      />
    </div>
    <div
      v-if="loading"
      class="agent-configuration__sections skeleton"
      aria-hidden="true"
    >
      <div
        v-for="registeredSection in registeredSections"
        :key="registeredSection.type"
        class="agent-configuration__skeleton-row"
      >
        <SkeletonBlock width="16px" height="16px" />
        <div class="agent-configuration__section-content">
          <SkeletonBlock width="120px" />
          <SkeletonBlock class="margin-top-1" width="180px" height="10px" />
        </div>
      </div>
    </div>
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
      <MenuList
        v-if="!selectedSection"
        class="agent-configuration__sections"
        :items="sectionItems"
        @select="section = $event.id"
      >
        <template #item-meta="{ item }">
          <Icon
            v-if="item.error"
            v-tooltip="item.error"
            tooltip-position="bottom-left"
            class="agent-configuration__section-status"
            icon="iconoir-warning-circle"
            type="error"
            size="small"
            role="img"
            :aria-label="item.error"
          />
          <Icon
            v-else
            class="agent-configuration__section-status"
            icon="iconoir-nav-arrow-right"
            type="secondary"
            size="small"
            aria-hidden="true"
          />
        </template>
      </MenuList>
      <ReadOnlyForm
        v-else
        :read-only="!editable"
        class="agent-configuration__form"
      >
        <form class="agent-configuration__body" @submit.prevent>
          <component
            :is="selectedSection.component"
            ref="sectionComponent"
            :section-type="selectedSection"
            :name="name"
            :configuration="configuration"
            :errors="errors"
            :enabled-models="enabledModels"
            :editable="editable"
            :availability-loading="availabilityLoading"
            @update:name="$emit('update:name', $event)"
            @rename="$emit('rename')"
            @change="$emit('change', $event)"
            @flush="$emit('flush')"
          />
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
import MenuList from '@baserow/modules/core/components/MenuList'
import Icon from '@baserow/modules/core/components/Icon'
import ButtonText from '@baserow/modules/core/components/ButtonText'

const props = defineProps({
  name: { type: String, required: true },
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
defineEmits(['close', 'update:name', 'rename', 'change', 'flush', 'reload'])
const { $registry } = useNuxtApp()
const section = ref(null)
const sectionComponent = ref(null)
const registeredSections = computed(() =>
  $registry.getOrderedList('agentConfigurationSection')
)
const selectedSection = computed(() =>
  registeredSections.value.find(
    (registered) => registered.type === section.value
  )
)
const sectionItems = computed(() =>
  registeredSections.value.map((registered) => ({
    id: registered.type,
    label: registered.name,
    description: registered.description,
    icon: registered.icon,
    error: registered.getErrorMessage(props.errors, props.configuration),
  }))
)

async function focusField(field) {
  const matchingSection = registeredSections.value.find((registered) =>
    Object.hasOwn(registered.fields, field)
  )
  if (!matchingSection) return
  section.value = matchingSection.type
  await nextTick()
  sectionComponent.value?.focusField?.(field)
}

defineExpose({ focusField })
</script>
