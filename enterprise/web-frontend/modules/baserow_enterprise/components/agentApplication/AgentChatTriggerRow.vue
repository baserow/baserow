<template>
  <div class="agent-chat-card agent-chat-trigger">
    <a class="agent-chat-card__header" @click.prevent="expanded = !expanded">
      <i :class="icon" class="agent-chat-card__icon"></i>
      <span class="agent-chat-card__title">
        {{ $t('agentChat.startedBy', { label }) }}
      </span>
      <i
        class="iconoir-nav-arrow-right agent-chat-card__chevron"
        :class="{ 'agent-chat-card__chevron--expanded': expanded }"
      ></i>
    </a>
    <div v-if="expanded" class="agent-chat-card__body">
      <template v-if="preview">
        <SegmentControl
          class="agent-chat-segment"
          :segments="segments"
          :active-index="rawShown ? 1 : 0"
          @update:active-index="rawShown = $event === 1"
        ></SegmentControl>
        <template v-if="!rawShown">
          <div v-if="preview.quote" class="agent-chat-quote">
            <div class="agent-chat-quote__head">
              <Avatar
                :initials="initials(preview.quote.author)"
                color="purple"
                size="x-small"
                rounded
              />
              <span class="agent-chat-quote__author">{{
                preview.quote.author
              }}</span>
              <span class="agent-chat-quote__time">{{ preview.quote.at }}</span>
            </div>
            <div class="agent-chat-quote__text">{{ preview.quote.text }}</div>
          </div>
          <AgentKeyValueList
            v-if="preview.fields.length > 0"
            :fields="preview.fields"
          />
          <AgentPreviewTable v-if="preview.table" :table="preview.table" />
          <div v-if="preview.body" class="agent-chat-preview-body">
            {{ preview.body }}
          </div>
        </template>
        <pre v-else class="agent-chat-trigger__payload">{{ raw }}</pre>
      </template>
      <pre v-else class="agent-chat-trigger__payload">{{ raw }}</pre>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, computed } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from '#imports'
import moment from '@baserow/modules/core/moment'
import AgentKeyValueList from '@baserow_enterprise/components/agentApplication/AgentKeyValueList'
import AgentPreviewTable from '@baserow_enterprise/components/agentApplication/AgentPreviewTable'
import { buildTriggerPreview } from '@baserow_enterprise/utils/agentTriggerPreview'
import { formatToolPayload } from '@baserow_enterprise/utils/agentChatEvents'

const TRIGGER_ICONS = {
  row_comment_created: 'iconoir-chat-bubble-empty',
  periodic: 'iconoir-timer',
  http_trigger: 'iconoir-globe',
  email_trigger: 'iconoir-mail',
}

export default defineComponent({
  name: 'AgentChatTriggerRow',
  components: { AgentKeyValueList, AgentPreviewTable },
  props: {
    label: {
      type: String,
      required: true,
    },
    triggerType: {
      type: String,
      required: false,
      default: '',
    },
    // The event payload; the opening message text when there is none.
    payload: {
      type: [Object, Array, String, Number, Boolean],
      required: false,
      default: null,
    },
    fallback: {
      type: String,
      required: false,
      default: '',
    },
  },
  setup(props) {
    const store = useStore()
    const { t } = useI18n()
    const expanded = ref(false)
    const rawShown = ref(false)

    const type = computed(() =>
      String(props.triggerType || '').replace(/^local_baserow_/, '')
    )
    const icon = computed(() => TRIGGER_ICONS[type.value] || 'iconoir-db')
    const segments = computed(() => [
      { label: t('agentChatTrigger.preview') },
      { label: t('agentChatTrigger.rawData') },
    ])

    const findTable = (tableId) => {
      for (const application of store.getters['application/getAll']) {
        const table = (application.tables || []).find(
          (item) => item.id === tableId
        )
        if (table) {
          return { application, table }
        }
      }
      return null
    }
    const helpers = {
      t,
      formatDate: (value) => (value ? moment(value).calendar() : ''),
      tableLabel: (tableId) => {
        const found = findTable(tableId)
        return found
          ? `${found.application.name} › ${found.table.name}`
          : tableId
            ? t('agentChatTrigger.tableId', { id: tableId })
            : ''
      },
      rowLabel: (tableId, rowId) =>
        rowId ? t('agentChatTrigger.rowId', { id: rowId }) : '',
    }
    const preview = computed(() =>
      buildTriggerPreview(type.value, props.payload, helpers)
    )
    const raw = computed(() =>
      props.payload !== null && props.payload !== undefined
        ? formatToolPayload(props.payload)
        : props.fallback
    )
    const initials = (name) => (name || '?').slice(0, 1).toUpperCase()

    return { expanded, rawShown, icon, segments, preview, raw, initials }
  },
})
</script>
