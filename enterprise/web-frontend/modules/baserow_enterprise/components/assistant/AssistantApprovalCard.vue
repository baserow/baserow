<template>
  <div
    class="assistant-approval"
    :class="`assistant-approval--${approval.status}`"
    role="group"
    :aria-label="approval.title"
  >
    <div class="assistant-approval__header">
      <i class="iconoir-shield-check assistant-approval__icon"></i>
      <span class="assistant-approval__title">{{ approval.title }}</span>
    </div>
    <ul v-if="approval.changes?.length" class="assistant-approval__changes">
      <li
        v-for="(change, index) in approval.changes"
        :key="index"
        class="assistant-approval__change"
      >
        {{ change }}
      </li>
    </ul>
    <template v-if="approval.status === 'pending'">
      <textarea
        v-if="rejecting"
        ref="reasonInput"
        v-model="reason"
        class="assistant-approval__reason"
        rows="2"
        :placeholder="$t('assistantApprovalCard.reasonPlaceholder')"
      ></textarea>
      <div class="assistant-approval__actions">
        <template v-if="!rejecting">
          <Button
            type="primary"
            size="small"
            :loading="deciding"
            @click="decide(true)"
            >{{ $t('assistantApprovalCard.approve') }}</Button
          >
          <Button
            type="secondary"
            size="small"
            :disabled="deciding"
            @click="startRejecting"
            >{{ $t('assistantApprovalCard.reject') }}</Button
          >
        </template>
        <template v-else>
          <Button
            type="danger"
            size="small"
            :loading="deciding"
            @click="decide(false)"
            >{{ $t('assistantApprovalCard.confirmReject') }}</Button
          >
          <Button
            type="ghost"
            size="small"
            :disabled="deciding"
            @click="rejecting = false"
            >{{ $t('assistantApprovalCard.cancel') }}</Button
          >
        </template>
      </div>
    </template>
    <div v-else class="assistant-approval__outcome">
      {{
        approval.status === 'approved'
          ? $t('assistantApprovalCard.approved')
          : $t('assistantApprovalCard.rejected')
      }}<template v-if="approval.reason">: {{ approval.reason }}</template>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  approval: { type: Object, required: true },
})

const store = useStore()
const { t } = useI18n()
const rejecting = ref(false)
const deciding = ref(false)
const reason = ref('')
const reasonInput = ref(null)

async function startRejecting() {
  rejecting.value = true
  await nextTick()
  reasonInput.value?.focus()
}

async function decide(approved) {
  deciding.value = true
  try {
    await store.dispatch('assistant/decideApprovals', [
      {
        id: props.approval.id,
        approved,
        ...(approved ? {} : { reason: reason.value.trim() }),
      },
    ])
  } catch {
    store.dispatch('toast/error', {
      title: t('assistantApprovalCard.decideFailed'),
    })
  } finally {
    deciding.value = false
  }
}
</script>
