<template>
  <p class="agent-create__intro">{{ $t('agent.setupReviewIntro') }}</p>
  <FormGroup :label="$t('agent.instructions')" small-label required>
    <FormTextarea
      :model-value="modelValue.instructions"
      :rows="6"
      @update:model-value="update({ instructions: $event })"
    />
  </FormGroup>
  <FormGroup
    class="agent-create__section"
    :label="$t('agent.setupHowItStarts')"
    :helper-text="isScheduled ? $t('agent.setupScheduleHint') : null"
    small-label
    required
  >
    <SegmentControl
      class="agent-create__start"
      :segments="startSegments"
      :active-index="START_OPTIONS.indexOf(modelValue.start)"
      @update:active-index="update({ start: START_OPTIONS[$event] })"
    />
    <div v-if="isScheduled" class="agent-create__schedule">
      <i class="agent-create__schedule-icon" :class="periodicType.icon"></i>
      <div>
        <div class="agent-create__schedule-name">{{ scheduleName }}</div>
        <div class="agent-create__schedule-description">
          {{ $t('agent.setupScheduleDescription') }}
        </div>
      </div>
    </div>
  </FormGroup>
  <FormGroup
    class="agent-create__section"
    :label="$t('agent.setupActsAs')"
    small-label
    required
  >
    <PaginatedDropdown
      class="agent-create__acts-as"
      :value="actsAsValue"
      :fetch-page="fetchIdentities"
      :add-empty-item="false"
      include-display-name-in-selected-event
      fetch-on-open
      refresh-on-open
      :disabled="!canBindIdentity"
      fixed-items
      @input="chooseActsAs"
    >
      <template #selectedValue>
        <i class="dropdown__selected-icon" :class="actsAsIcon"></i>
        <span class="dropdown__selected-text">{{ actsAsName }}</span>
        <Badge v-if="actsAsRole" class="agent-create__role" size="small">
          {{ actsAsRole.name }}
        </Badge>
      </template>
      <template #items="{ results }">
        <DropdownItem
          v-if="canCreateIdentity"
          :value="SETUP_ACTS_AS.NEW"
          :name="newIdentityName"
          :description="$t('agent.setupNewIdentityDescription')"
        >
          <i class="select__item-icon" :class="identityIcon"></i>
          <span class="select__item-name-text">{{ newIdentityName }}</span>
          <Badge v-if="newIdentityRole" class="agent-create__role" size="small">
            {{ newIdentityRole.name }}
          </Badge>
        </DropdownItem>
        <DropdownItem
          v-for="identity in results"
          :key="identity.id"
          :value="identity.id"
          :name="$t('agent.setupUseIdentity', { name: identity.name })"
          :description="$t('agent.setupUseIdentityDescription')"
        >
          <i class="select__item-icon" :class="identityIcon"></i>
          <span class="select__item-name-text">{{
            $t('agent.setupUseIdentity', { name: identity.name })
          }}</span>
          <Badge
            v-if="roleOf(identity.role_uid)"
            class="agent-create__role"
            size="small"
          >
            {{ roleOf(identity.role_uid).name }}
          </Badge>
        </DropdownItem>
        <DropdownItem
          :value="SETUP_ACTS_AS.NONE"
          :name="$t('agent.noWorkspaceAccess')"
          :description="$t('agent.setupNoWorkspaceAccessDescription')"
          icon="iconoir-prohibition"
        />
      </template>
      <template v-if="canCreateIdentity" #footer="{ hide }">
        <div class="select__footer">
          <button
            type="button"
            class="select__footer-button"
            @click="addIdentity(hide)"
          >
            <i class="iconoir-plus" aria-hidden="true"></i>
            {{ $t('agent.addIdentity') }}
          </button>
        </div>
      </template>
    </PaginatedDropdown>
  </FormGroup>
  <FormGroup
    class="agent-create__section"
    :label="$t('agent.setupPermissions')"
    :helper-text="
      hasIdentity
        ? $t('agent.setupPermissionsHint')
        : $t('agent.toolsRequireIdentity')
    "
    small-label
    required
  >
    <Dropdown
      class="agent-create__permissions"
      :model-value="modelValue.permissions"
      :disabled="!hasIdentity"
      :show-search="false"
      fixed-items
      @update:model-value="choosePermissions"
    >
      <template v-if="isCustom" #selectedValue>
        <i class="dropdown__selected-icon" :class="CUSTOM_ICON"></i>
        <span class="dropdown__selected-text">{{ customSummary }}</span>
      </template>
      <DropdownItem
        v-for="preset in PERMISSION_PRESETS"
        :key="preset.value"
        :value="preset.value"
        :name="$t(preset.label)"
        :icon="preset.icon"
      />
      <DropdownItem
        v-if="availableTools.length"
        :value="SETUP_PERMISSIONS.CUSTOM"
        :name="$t('agent.setupPermissionsCustom')"
        :icon="CUSTOM_ICON"
      />
    </Dropdown>
  </FormGroup>
  <FormGroup
    v-if="actionTypes.length"
    class="agent-create__section"
    :label="$t('agent.setupExtras')"
    small-label
    required
  >
    <ul class="agent-create__extras">
      <li
        v-for="serviceType in actionTypes"
        :key="serviceType.getType()"
        class="agent-create__extra"
      >
        <i class="agent-create__extra-icon" :class="serviceType.icon"></i>
        <div class="agent-create__extra-text">
          <div class="agent-create__extra-name">{{ serviceType.name }}</div>
          <div class="agent-create__extra-description">
            {{ serviceType.description }}
          </div>
        </div>
        <SwitchInput
          small
          :model-value="modelValue.actionTypes.includes(serviceType.getType())"
          :aria-label="serviceType.name"
          @update:model-value="toggleAction(serviceType.getType(), $event)"
        />
      </li>
    </ul>
  </FormGroup>
  <ManageIdentityModal
    v-if="canCreateIdentity"
    ref="createIdentityModal"
    :workspace="workspace"
    :initial-role-uid="newIdentityRole?.uid"
    @saved="selectIdentity"
  />
  <AgentToolPermissionsModal
    ref="toolPermissionsModal"
    :workspace="workspace"
    :available-tools="availableTools"
    :allowed-tools="customToolsSeed.allowed_tools"
    :ask-first-tools="customToolsSeed.ask_first_tools"
    :agent-name="modelValue.name"
    editable
    @save="
      update({ permissions: SETUP_PERMISSIONS.CUSTOM, customTools: $event })
    "
  />
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes'
import IdentityService from '@baserow/modules/core/services/identity'
import ManageIdentityModal from '@baserow/modules/core/components/settings/identities/ManageIdentityModal'
import AgentToolPermissionsModal from '@baserow/modules/agent/components/configuration/AgentToolPermissionsModal'
import { usableAgentTools } from '@baserow/modules/agent/agentTools'
import {
  SCHEDULE_TRIGGER_TYPE,
  SETUP_ACTS_AS,
  SETUP_PERMISSIONS,
  SETUP_START,
  scheduleValues,
  setupActionTypes,
  toolsForPermissions,
} from '@baserow/modules/agent/utils/agentSetup'

const START_OPTIONS = [SETUP_START.CHAT, SETUP_START.SCHEDULE]
const PERMISSION_PRESETS = [
  {
    value: SETUP_PERMISSIONS.READ,
    label: 'agent.setupPermissionsRead',
    icon: 'iconoir-eye-empty',
  },
  {
    value: SETUP_PERMISSIONS.ASK,
    label: 'agent.setupPermissionsAsk',
    icon: 'iconoir-shield-check',
  },
  {
    value: SETUP_PERMISSIONS.CHANGE,
    label: 'agent.setupPermissionsChange',
    icon: 'iconoir-edit-pencil',
  },
]
const CUSTOM_ICON = 'iconoir-settings'

const props = defineProps({
  modelValue: { type: Object, required: true },
  workspace: { type: Object, required: true },
  availableTools: { type: Array, required: true },
  canBindIdentity: Boolean,
  canCreateIdentity: Boolean,
  newIdentityRole: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const { $client, $registry } = useNuxtApp()

const identityIcon = $registry.get(
  'subject',
  UserSubjectType.getType()
).identityIconClass
const createIdentityModal = ref(null)
const toolPermissionsModal = ref(null)
const actionTypes = computed(() => setupActionTypes($registry, props.workspace))
const periodicType = $registry.get('service', SCHEDULE_TRIGGER_TYPE)
const scheduleName = computed(() =>
  periodicType.getDefaultName(
    scheduleValues($registry, props.modelValue.schedule)
  )
)
const startSegments = computed(() => [
  { label: t('agent.setupStartChat') },
  { label: t('agent.setupStartSchedule') },
])
const isScheduled = computed(
  () => props.modelValue.start === SETUP_START.SCHEDULE
)
const hasIdentity = computed(
  () => props.modelValue.actsAs.kind !== SETUP_ACTS_AS.NONE
)
const newIdentityName = computed(() =>
  t('agent.setupNewIdentity', { name: props.modelValue.name })
)

const roleOf = (uid) =>
  (props.workspace._?.roles || []).find((role) => role.uid === uid) || null

const actsAsValue = computed(() => {
  const { actsAs } = props.modelValue
  return actsAs.kind === SETUP_ACTS_AS.EXISTING ? actsAs.id : actsAs.kind
})
const actsAsIcon = computed(() =>
  hasIdentity.value ? identityIcon : 'iconoir-prohibition'
)
const actsAsName = computed(() => {
  const { actsAs } = props.modelValue
  if (actsAs.kind === SETUP_ACTS_AS.NEW) return newIdentityName.value
  if (actsAs.kind === SETUP_ACTS_AS.EXISTING)
    return t('agent.setupUseIdentity', { name: actsAs.name })
  return t('agent.noWorkspaceAccess')
})
const actsAsRole = computed(() => {
  const { actsAs } = props.modelValue
  if (actsAs.kind === SETUP_ACTS_AS.NEW) return props.newIdentityRole
  if (actsAs.kind === SETUP_ACTS_AS.EXISTING) return roleOf(actsAs.roleUid)
  return null
})

const isCustom = computed(
  () => props.modelValue.permissions === SETUP_PERMISSIONS.CUSTOM
)
const customToolsSeed = computed(
  () =>
    props.modelValue.customTools ??
    toolsForPermissions(props.availableTools, props.modelValue.permissions)
)
const customSummary = computed(() =>
  t('agent.setupPermissionsCustomSummary', {
    on: props.modelValue.customTools.allowed_tools.length,
    total: usableAgentTools(props.availableTools).length,
    count: props.modelValue.customTools.ask_first_tools.length,
  })
)

function update(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}

function choosePermissions(value) {
  if (value === SETUP_PERMISSIONS.CUSTOM) toolPermissionsModal.value.show()
  else update({ permissions: value })
}

function selectIdentity(identity) {
  update({
    actsAs: {
      kind: SETUP_ACTS_AS.EXISTING,
      id: identity.id,
      name: identity.name,
      roleUid: identity.role_uid,
    },
  })
}

function chooseActsAs({ value, item }) {
  if (value === SETUP_ACTS_AS.NEW || value === SETUP_ACTS_AS.NONE) {
    update({ actsAs: { kind: value } })
  } else if (item) {
    selectIdentity(item)
  }
}

function fetchIdentities(page, search) {
  return IdentityService($client).listPage(props.workspace.id, {
    page,
    search,
    forSelection: true,
  })
}

function addIdentity(hide) {
  hide()
  createIdentityModal.value.show()
}

function toggleAction(type, enabled) {
  const others = props.modelValue.actionTypes.filter((item) => item !== type)
  update({ actionTypes: enabled ? [...others, type] : others })
}
</script>
