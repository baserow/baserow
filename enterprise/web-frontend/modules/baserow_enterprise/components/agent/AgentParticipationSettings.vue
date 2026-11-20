<template>
  <div class="agent-participation">
    <FormGroup
      v-for="capability in AGENT_CAPABILITIES"
      :key="capability"
      class="margin-bottom-2"
      :label="$t('agentPermissions.' + capability)"
      required
      small-label
    >
      <Button
        v-if="!licensed"
        type="secondary"
        button-type="button"
        icon="iconoir-lock"
        :disabled="!editable"
        @click="paywall.show()"
        >{{ roleLabel(AGENT_UNLICENSED_ROLES[capability]) }}</Button
      >
      <PermissionRoleSelect
        v-else
        :model-value="pendingRoles[capability] ?? rules?.[capability].role"
        :options="roleOptions(capability)"
        size="regular"
        :placeholder="$t('agentPermissions.loading')"
        :disabled="
          !editable || !rules || !!pendingRoles[capability] || loadError
        "
        :loading="!!pendingRoles[capability]"
        @update:model-value="chooseRole(capability, $event)"
      />
      <ButtonText
        v-if="licensed && editable && rules?.[capability].role === 'CUSTOM'"
        size="small"
        type="secondary"
        button-type="button"
        icon="iconoir-group"
        class="margin-top-1"
        :disabled="!!pendingRoles[capability] || loadError"
        @click="openPeople(capability)"
        >{{ $t('agentPermissions.managePeople') }}</ButtonText
      >
      <template v-if="licensed && problems[capability]" #warning>{{
        problems[capability]
      }}</template>
    </FormGroup>
    <p v-if="!licensed" class="agent-participation__note">
      {{ $t('agentPermissions.unlicensedNote') }}
    </p>
    <Alert v-if="licensed && loadError" type="error">
      {{ $t('agentPermissions.loadError') }}
      <template #actions
        ><ButtonText button-type="button" @click="load">{{
          $t('action.retry')
        }}</ButtonText></template
      >
    </Alert>
    <Modal ref="peopleModal" small :can-close="!pendingRoles[editingPeople]">
      <h2 class="box__title">{{ $t('agentPermissions.' + editingPeople) }}</h2>
      <FieldPermissionSubjectsSelector
        v-if="licensed && editingPeople"
        ref="selector"
        :subjects="rules?.[editingPeople]?.subjects"
        :fetch-options="fetchOptions"
        :disabled="!!pendingRoles[editingPeople] || !editable || loadError"
        :minimum-selection="1"
        copy-prefix="agentPermissionSubjects"
        @edit="saveRule(editingPeople, 'CUSTOM', $event)"
      />
    </Modal>
    <PaidFeaturesModal
      v-if="workspace"
      ref="paywall"
      :workspace="workspace"
      initial-selected-type="rbac"
    />
  </div>
</template>
<script setup>
import { computed, inject, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStore } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { injectAgentTriggers } from '@baserow/modules/agent/composables/useAgentTriggers'
import EnterpriseFeatures from '@baserow_enterprise/features'
import AgentPermissionsService from '@baserow_enterprise/services/agentPermissions'
import {
  AGENT_CAPABILITIES,
  AGENT_DEFAULT_ROLES,
  AGENT_UNLICENSED_ROLES,
  agentRuleProblems,
} from '@baserow_enterprise/utils/agentPermissions'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import FieldPermissionSubjectsSelector from '@baserow_enterprise/components/fieldPermissions/FieldPermissionSubjectsSelector'
import PermissionRoleSelect from '@baserow_enterprise/components/fieldPermissions/PermissionRoleSelect'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  /** Whether the user may change the rules. */
  editable: Boolean,
})
const ROLES = ['EDITOR', 'BUILDER', 'ADMIN', 'CUSTOM', 'NOBODY']
const { $client, $hasFeature } = useNuxtApp()
const { t } = useI18n()
const store = useStore()
const agent = inject('agentApplication')
const agentTriggers = reactive(injectAgentTriggers())
const workspace = computed(() =>
  agent.value ? store.getters['workspace/get'](agent.value.workspace.id) : null
)
const licensed = computed(() =>
  Boolean(
    workspace.value && $hasFeature(EnterpriseFeatures.RBAC, workspace.value.id)
  )
)
const stored = computed(() =>
  store.getters['agentParticipationRules/get'](agent.value.id)
)
const rules = computed(() => stored.value?.rules || null)
const loadError = computed(() => Boolean(stored.value?.loadError))
const problems = computed(() =>
  agentRuleProblems(t, rules.value, agentTriggers)
)
const peopleModal = ref(null)
const paywall = ref(null)
const selector = ref(null)
const editingPeople = ref(null)
const pendingRoles = reactive({})

function roleLabel(role) {
  return ['BUILDER', 'ADMIN'].includes(role)
    ? t('fieldPermissionModal.' + role.toLowerCase() + 'Title')
    : t('agentPermissions.' + role)
}

function roleOptions(capability) {
  return ROLES.filter(
    (uid) => !(uid === 'NOBODY' && capability === 'approve')
  ).map((uid) => ({
    uid,
    title: roleLabel(uid),
    desc:
      uid === AGENT_DEFAULT_ROLES[capability]
        ? t('agentPermissions.default')
        : null,
  }))
}

function load() {
  store.dispatch('agentParticipationRules/fetch', { agentId: agent.value.id })
}

function openPeople(capability) {
  editingPeople.value = capability
  peopleModal.value.show()
}

function chooseRole(capability, role) {
  if (!props.editable || pendingRoles[capability] || !rules.value) return
  if (role === 'CUSTOM') openPeople(capability)
  else if (role !== rules.value[capability].role) {
    saveRule(capability, role, [])
  }
}

function fetchOptions(params) {
  return AgentPermissionsService($client).fetchSubjectOptions(
    agent.value.id,
    params
  )
}

async function saveRule(capability, role, subjects) {
  if (!props.editable || !licensed.value || pendingRoles[capability]) return
  pendingRoles[capability] = role
  try {
    await store.dispatch('agentParticipationRules/save', {
      agentId: agent.value.id,
      capability,
      role,
      subjects,
    })
  } catch (error) {
    if (editingPeople.value === capability) selector.value?.reset()
    notifyIf(error)
    return
  } finally {
    delete pendingRoles[capability]
  }
  try {
    await store.dispatch('workspace/forceFetchPermissions', workspace.value)
  } catch (error) {
    notifyIf(error)
  }
}
</script>
