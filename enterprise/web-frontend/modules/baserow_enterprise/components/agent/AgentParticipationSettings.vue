<template>
  <div class="margin-bottom-3">
    <FormGroup
      v-for="capability in capabilities"
      :key="capability"
      class="margin-bottom-2"
      :label="$t('agentPermissions.' + capability)"
      :helper-text="
        capability === 'approve' ? $t('agentPermissions.approveHelp') : ''
      "
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
        >{{ roleLabel('EDITOR') }}</Button
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
      <template
        v-if="
          rules?.[capability].role === 'NOBODY' &&
          (capability === 'approve' || !hasEnabledTrigger)
        "
        #warning
        >{{
          $t(
            capability === 'approve'
              ? 'agentPermissions.noApproval'
              : 'agentPermissions.triggerPaused'
          )
        }}</template
      >
    </FormGroup>
    <Alert v-if="loadError" type="error">
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
      ref="paywall"
      :workspace="workspace"
      initial-selected-type="rbac"
    />
  </div>
</template>
<script setup>
import isEqual from 'lodash/isEqual'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStore } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import FieldPermissionSubjectsSelector from '@baserow_enterprise/components/fieldPermissions/FieldPermissionSubjectsSelector'
import PermissionRoleSelect from '@baserow_enterprise/components/fieldPermissions/PermissionRoleSelect'

const props = defineProps({
  agent: { type: Object, required: true },
  workspace: { type: Object, required: true },
  editable: Boolean,
  hasTrigger: Boolean,
  hasEnabledTrigger: Boolean,
})
const capabilities = ['chat', 'approve']
const { $client, $hasFeature } = useNuxtApp()
const { t } = useI18n()
const store = useStore()
const licensed = computed(() =>
  $hasFeature(EnterpriseFeatures.RBAC, props.workspace.id)
)
const base = computed(() => '/agent-permissions/' + props.agent.id + '/')
const rules = ref(null)
const peopleModal = ref(null)
const paywall = ref(null)
const selector = ref(null)
const editingPeople = ref(null)
const pendingRoles = reactive({})
const loadError = ref(false)
let revision = 0

function roleLabel(role) {
  return ['CUSTOM', 'NOBODY'].includes(role)
    ? t('agentPermissions.' + role)
    : t('fieldPermissionModal.' + role.toLowerCase() + 'Title')
}

function roleOptions(capability) {
  return ['EDITOR', 'BUILDER', 'ADMIN', 'CUSTOM', 'NOBODY'].map((uid) => {
    const disabled =
      uid === 'NOBODY' && capability === 'chat' && !props.hasTrigger
    return {
      uid,
      title: roleLabel(uid),
      disabled,
      desc: disabled ? t('agentPermissions.needsTrigger') : null,
    }
  })
}

async function load() {
  const request = ++revision
  loadError.value = false
  if (!licensed.value) {
    rules.value = null
    return
  }
  try {
    const { data } = await $client.get(base.value)
    if (request !== revision) return
    if (!rules.value) rules.value = {}
    // Keeping unchanged subjects preserves an open picker across permission refreshes.
    for (const capability of capabilities) {
      if (!isEqual(rules.value[capability], data[capability])) {
        rules.value[capability] = data[capability]
      }
    }
  } catch (error) {
    if (request === revision) {
      loadError.value = true
      notifyIf(error)
    }
  }
}
watch([licensed, () => props.workspace._?.permissions], load, {
  immediate: true,
})

function openPeople(capability) {
  editingPeople.value = capability
  peopleModal.value.show()
}

function chooseRole(capability, role) {
  if (!props.editable || pendingRoles[capability] || !rules.value) return
  if (role === 'CUSTOM') openPeople(capability)
  else if (
    role !== rules.value[capability].role &&
    !(role === 'NOBODY' && capability === 'chat' && !props.hasTrigger)
  ) {
    saveRule(capability, role, [])
  }
}

function fetchOptions(params) {
  return $client.get(base.value + 'options/', { params })
}

async function saveRule(capability, role, subjects) {
  if (!props.editable || !licensed.value || pendingRoles[capability]) return
  pendingRoles[capability] = role
  try {
    const { data } = await $client.put(base.value + capability + '/', {
      role,
      subjects,
    })
    // An earlier permissions refresh may still contain the previous rule.
    revision++
    if (rules.value) rules.value[capability] = data
  } catch (error) {
    if (editingPeople.value === capability) selector.value?.reset()
    notifyIf(error)
    return
  } finally {
    delete pendingRoles[capability]
  }
  try {
    await store.dispatch('workspace/forceFetchPermissions', props.workspace)
  } catch (error) {
    notifyIf(error)
  }
}
</script>
