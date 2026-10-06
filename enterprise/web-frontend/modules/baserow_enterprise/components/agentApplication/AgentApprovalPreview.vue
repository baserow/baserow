<template>
  <div class="agent-approval-preview">
    <template v-if="preview.kind === 'email'">
      <div class="agent-mail-card">
        <div class="agent-mail-card__head">
          <div
            v-for="field in emailFields"
            :key="field.key"
            class="agent-mail-card__line"
          >
            <span class="agent-mail-card__key">{{ field.key }}</span>
            <span class="agent-mail-card__value">
              <Avatar
                v-if="field.identity"
                :initials="field.identity.slice(0, 1).toUpperCase()"
                color="green"
                size="x-small"
                rounded
              />
              {{ field.value }}
            </span>
          </div>
        </div>
        <div v-if="preview.body" class="agent-mail-card__body">
          {{ preview.body }}
        </div>
      </div>
      <div v-if="footnote" class="agent-approval-preview__footnote">
        <i class="iconoir-mail"></i>
        {{ footnote }}
      </div>
    </template>
    <AgentPreviewTable v-else-if="preview.kind === 'table'" :table="preview" />
    <template v-else-if="preview.kind === 'args'">
      <AgentKeyValueList
        v-if="preview.fields.length > 0"
        :fields="preview.fields"
      />
      <AgentPreviewTable v-if="preview.table" :table="preview.table" />
    </template>
    <AgentKeyValueList
      v-else-if="preview.kind === 'fields' && preview.fields.length > 0"
      :fields="preview.fields"
    />
  </div>
</template>

<script>
import AgentKeyValueList from '@baserow_enterprise/components/agentApplication/AgentKeyValueList'
import AgentPreviewTable from '@baserow_enterprise/components/agentApplication/AgentPreviewTable'

const EMAIL_FIELDS = ['from', 'to', 'cc', 'bcc', 'subject']

/**
 * The preview of a tool approval: a mail card for email actions, a table for
 * row writes, label/value rows otherwise, or the arguments themselves when
 * the tool stored no preview.
 */
export default {
  name: 'AgentApprovalPreview',
  components: { AgentKeyValueList, AgentPreviewTable },
  props: {
    preview: {
      type: Object,
      required: true,
    },
    footnote: {
      type: String,
      required: false,
      default: '',
    },
  },
  computed: {
    emailFields() {
      return EMAIL_FIELDS.filter((key) => this.preview[key]).map((key) => {
        const value = String(this.preview[key])
        const fromName = key === 'from' ? this.preview.from_name : ''
        return {
          key: this.$t(`agentToolApprovals.email_${key}`),
          value: fromName ? `${fromName} <${value}>` : value,
          identity: key === 'from' ? fromName : '',
        }
      })
    },
  },
}
</script>
