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
    <Dropdown
      class="agent-create__acts-as"
      :model-value="actsAsValue"
      :show-search="false"
      fixed-items
      @update:model-value="chooseActsAs"
    >
      <template #selectedValue>
        <i class="dropdown__selected-icon" :class="actsAsIcon"></i>
        <span class="dropdown__selected-text">{{ actsAsName }}</span>
        <Badge v-if="actsAsRole" class="agent-create__role" size="small">
          {{ actsAsRole.name }}
        </Badge>
      </template>
      <DropdownItem
        v-if="canCreateIdentity"
        :value="SETUP_ACTS_AS.NEW"
        :name="newIdentityName"
        :description="$t('agent.setupNewIdentityDescription')"
      >
        <i class="select__item-icon baserow-icon-agent"></i>
        <span class="select__item-name-text">{{ newIdentityName }}</span>
        <Badge v-if="newIdentityRole" class="agent-create__role" size="small">
          {{ newIdentityRole.name }}
        </Badge>
      </DropdownItem>
      <DropdownItem
        v-for="identity in identities"
        :key="identity.id"
        :value="existingValue(identity.id)"
        :name="$t('agent.setupUseIdentity', { name: identity.name })"
        :description="$t('agent.setupUseIdentityDescription')"
      >
        <i class="select__item-icon baserow-icon-agent"></i>
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
    </Dropdown>
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
      @update:model-value="update({ permissions: $event })"
    >
      <DropdownItem
        v-for="preset in PERMISSION_PRESETS"
        :key="preset.value"
        :value="preset.value"
        :name="$t(preset.label)"
        :icon="preset.icon"
      />
    </Dropdown>
  </FormGroup>
  <FormGroup
    class="agent-create__section"
    :label="$t('agent.setupExtras')"
    small-label
    required
  >
    <ul class="agent-create__extras">
      <li class="agent-create__extra">
        <i class="agent-create__extra-icon iconoir-globe"></i>
        <div class="agent-create__extra-text">
          <div class="agent-create__extra-name">
            {{ $t('agent.webSearch') }}
          </div>
          <div class="agent-create__extra-description">
            {{ $t('agent.setupWebSearchDescription') }}
          </div>
        </div>
        <SwitchInput
          small
          :model-value="modelValue.webSearch"
          :aria-label="$t('agent.webSearch')"
          @update:model-value="update({ webSearch: $event })"
        />
      </li>
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
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import IdentityService from '@baserow/modules/core/services/identity'
import {
  SCHEDULE_TRIGGER_TYPE,
  SETUP_ACTS_AS,
  SETUP_PERMISSIONS,
  SETUP_START,
  newIdentityRoleUid,
  setupActionTypes,
} from '@baserow/modules/agent/utils/agentSetup'

const START_OPTIONS = [SETUP_START.CHAT, SETUP_START.SCHEDULE]
const PERMISSION_PRESETS = [
  {
    value: SETUP_PERMISSIONS.READ,
    label: 'agent.setupPermissionsRead',
    icon: 'iconoir-eye',
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
const EXISTING_PREFIX = `${SETUP_ACTS_AS.EXISTING}:`

const props = defineProps({
  modelValue: { type: Object, required: true },
  workspace: { type: Object, required: true },
  canCreateIdentity: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const { $client, $registry } = useNuxtApp()

const identities = ref([])
const actionTypes = computed(() => setupActionTypes($registry, props.workspace))
const periodicType = $registry.get('service', SCHEDULE_TRIGGER_TYPE)
const scheduleName = computed(() =>
  periodicType.getDefaultName(periodicType.getDefaultValues(null, {}))
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

const existingValue = (id) => `${EXISTING_PREFIX}${id}`
const roleOf = (uid) =>
  (props.workspace._?.roles || []).find((role) => role.uid === uid) || null
const newIdentityRole = computed(() => roleOf(props.modelValue.actsAs.roleUid))

const actsAsValue = computed(() => {
  const { actsAs } = props.modelValue
  return actsAs.kind === SETUP_ACTS_AS.EXISTING
    ? existingValue(actsAs.id)
    : actsAs.kind
})
const actsAsIcon = computed(() =>
  hasIdentity.value ? 'baserow-icon-agent' : 'iconoir-prohibition'
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
  if (actsAs.kind === SETUP_ACTS_AS.NEW) return newIdentityRole.value
  if (actsAs.kind === SETUP_ACTS_AS.EXISTING)
    return roleOf(
      identities.value.find((identity) => identity.id === actsAs.id)?.role_uid
    )
  return null
})

function update(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}

function chooseActsAs(value) {
  if (value === SETUP_ACTS_AS.NEW) {
    update({
      actsAs: {
        kind: SETUP_ACTS_AS.NEW,
        roleUid: newIdentityRoleUid(props.workspace),
      },
    })
  } else if (value === SETUP_ACTS_AS.NONE) {
    update({ actsAs: { kind: SETUP_ACTS_AS.NONE } })
  } else {
    const id = Number(value.slice(EXISTING_PREFIX.length))
    const identity = identities.value.find((item) => item.id === id)
    update({
      actsAs: { kind: SETUP_ACTS_AS.EXISTING, id, name: identity.name },
    })
  }
}

function toggleAction(type, enabled) {
  const others = props.modelValue.actionTypes.filter((item) => item !== type)
  update({ actionTypes: enabled ? [...others, type] : others })
}

onMounted(async () => {
  try {
    const { data } = await IdentityService($client).listPage(
      props.workspace.id,
      { forSelection: true }
    )
    identities.value = data.results
  } catch {
    identities.value = []
  }
})
</script>
