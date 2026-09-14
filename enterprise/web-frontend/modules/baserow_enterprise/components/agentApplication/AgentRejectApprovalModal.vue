<template>
  <Modal ref="modal" small>
    <div>
      <h2 class="box__title">{{ $t('agentToolApprovals.rejectTitle') }}</h2>
      <p class="agent-tool-approvals__reject-text">
        {{ $t('agentToolApprovals.rejectText', { step: stepLabel }) }}
      </p>
      <FormGroup>
        <FormInput
          ref="reasonInput"
          v-model="reason"
          :placeholder="$t('agentToolApprovals.reasonPlaceholder')"
          @keydown.enter="confirm"
        ></FormInput>
      </FormGroup>
      <div class="actions actions--right actions--gap">
        <Button type="secondary" @click="hide()">
          {{ $t('agentToolApprovals.cancel') }}
        </Button>
        <Button type="danger" @click="confirm">
          {{ $t('agentToolApprovals.reject') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'AgentRejectApprovalModal',
  mixins: [modal],
  emits: ['reject'],
  data() {
    return {
      approval: null,
      stepLabel: '',
      reason: '',
    }
  },
  methods: {
    show(approval, stepLabel, ...args) {
      this.approval = approval
      this.stepLabel = stepLabel
      this.reason = ''
      modal.methods.show.call(this, ...args)
      this.$nextTick(() => this.$refs.reasonInput?.focus())
    },
    confirm() {
      this.$emit('reject', {
        approval: this.approval,
        reason: this.reason.trim(),
      })
      this.hide()
    },
  },
}
</script>
