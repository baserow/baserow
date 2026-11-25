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
        :model-value="
          saving?.capability === capability
            ? saving.role
            : rules?.[capability].role
        "
        :options="roleOptions(capability)"
        size="regular"
        :placeholder="$t('agentPermissions.loading')"
        :disabled="!editable || !rules || !!saving || loadError"
        :loading="saving?.capability === capability"
        @update:model-value="chooseRole(capability, $event)"
      />
      <ButtonText
        v-if="licensed && editable && rules?.[capability].role === 'CUSTOM'"
        size="small"
        type="secondary"
        button-type="button"
        icon="iconoir-group"
        class="margin-top-1"
        :disabled="!!saving || loadError"
        @click="openPeople(capability)"
        >{{
          $t('agentPermissions.managePeople', {
            count: rules[capability].subjects.length,
          })
        }}</ButtonText
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
    <Modal ref="peopleModal" small :can-close="!saving">
      <h2 class="box__title">{{ $t('agentPermissions.' + editingPeople) }}</h2>
      <FieldPermissionSubjectsSelector
        v-if="licensed && editingPeople"
        ref="selector"
        :subjects="rules?.[editingPeople]?.subjects"
        :fetch-options="fetchOptions"
        :disabled="!!saving || !editable || loadError"
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
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStore } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
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
  /** The Permissions section type, which tells whether the rules apply. */
  sectionType: { type: Object, required: true },
  /** Whether the user may change the rules. */
  editable: Boolean,
})
const ROLES = ['EDITOR', 'BUILDER', 'ADMIN', 'CUSTOM', 'NOBODY']
const { $client } = useNuxtApp()
const { t } = useI18n()
const store = useStore()
const service = AgentPermissionsService($client)
const agent = inject('agentApplication')
const workspace = computed(() =>
  agent.value ? store.getters['workspace/get'](agent.value.workspace.id) : null
)
const licensed = computed(() => props.sectionType.isLicensed(workspace.value))
const rules = ref(null)
const loadError = ref(false)
/** The `{ capability, role }` being saved, or null. */
const saving = ref(null)
const problems = computed(() => agentRuleProblems(t, rules.value))
const peopleModal = ref(null)
const paywall = ref(null)
const selector = ref(null)
const editingPeople = ref(null)
let loadCount = 0

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

/** Loads the Agent's rules, ignoring a reply that a newer load replaced. */
async function load() {
  const current = ++loadCount
  rules.value = null
  loadError.value = false
  if (!licensed.value) return
  try {
    const { data } = await service.get(agent.value.id)
    if (current === loadCount) rules.value = data
  } catch (error) {
    if (current !== loadCount) return
    loadError.value = true
    notifyIf(error)
  }
}

onMounted(load)
watch([() => agent.value?.id, licensed], load)

function openPeople(capability) {
  editingPeople.value = capability
  peopleModal.value.show()
}

function chooseRole(capability, role) {
  if (!props.editable || saving.value || !rules.value) return
  if (role === 'CUSTOM') openPeople(capability)
  else if (role !== rules.value[capability].role) {
    saveRule(capability, role, [])
  }
}

function fetchOptions(params) {
  return service.fetchSubjectOptions(agent.value.id, params)
}

function notifySaveError(error) {
  if (!error.handler) throw error
  const message = error.handler.getMessage(null, {
    ERROR_AGENT_RULE_LEAVES_NO_APPROVER: new ResponseErrorMessage(
      t('agentPermissions.noApproverTitle'),
      t('agentPermissions.noApproverDescription')
    ),
  })
  error.handler.notifyIf(null, message)
}

async function saveRule(capability, role, subjects) {
  if (!props.editable || !licensed.value || saving.value) return
  saving.value = { capability, role }
  const current = loadCount
  try {
    const { data } = await service.update(agent.value.id, capability, {
      role,
      subjects,
    })
    if (current === loadCount) rules.value[capability] = data
  } catch (error) {
    if (editingPeople.value === capability) selector.value?.reset()
    notifySaveError(error)
  } finally {
    saving.value = null
  }
}
</script>
