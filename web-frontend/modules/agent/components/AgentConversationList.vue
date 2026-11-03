<template>
  <aside class="agent-conversations" :aria-busy="loading">
    <div class="agent-conversations__header">
      {{ $t('agent.recent') }}
    </div>
    <div class="agent-conversations__content">
      <div
        v-if="!error && loading && !items.length"
        class="skeleton"
        aria-hidden="true"
      >
        <div
          v-for="width in ['75%', '55%', '85%', '65%']"
          :key="width"
          class="agent-conversations__skeleton-row"
        >
          <SkeletonBlock width="16px" height="16px" shape="circle" />
          <SkeletonBlock :width="width" />
        </div>
      </div>
      <ul v-if="items.length" class="agent-conversations__list">
        <li v-for="item in items" :key="item.uuid">
          <button
            type="button"
            class="agent-conversations__item"
            :class="{
              'agent-conversations__item--selected': item.uuid === selected,
            }"
            :aria-current="item.uuid === selected ? 'true' : undefined"
            @click="$emit('select', item)"
          >
            <Icon
              icon="iconoir-chat-bubble"
              type="secondary"
              aria-hidden="true"
            />
            <span class="agent-conversations__item-name">{{
              item.title || $t('agent.newConversation')
            }}</span>
            <span v-if="item.local" class="agent-conversations__draft">{{
              $t('agent.draft')
            }}</span>
            <span
              class="agent-conversations__status"
              :class="
                item.run_id
                  ? 'agent-conversations__status--replying'
                  : 'agent-conversations__status--idle'
              "
              aria-hidden="true"
            />
          </button>
        </li>
      </ul>
      <Alert v-if="error" type="error" class="margin-top-2">
        {{ $t('agent.conversationsLoadError') }}
        <template #actions
          ><Button
            type="secondary"
            size="small"
            button-type="button"
            @click="$emit('retry')"
            >{{ $t('action.retry') }}</Button
          ></template
        >
      </Alert>
      <Button
        v-else-if="hasMore"
        type="secondary"
        size="small"
        button-type="button"
        :loading="loading"
        class="agent-conversations__more"
        @click="$emit('load-more')"
        >{{ $t('agent.loadMore') }}</Button
      >
    </div>
    <div v-if="canCreate" class="agent-conversations__footer">
      <Button
        type="secondary"
        button-type="button"
        icon="iconoir-plus"
        full-width
        :disabled="!readyToSend"
        @click="$emit('create')"
        >{{ $t('agent.newConversation') }}</Button
      >
    </div>
  </aside>
</template>

<script setup>
import Icon from '@baserow/modules/core/components/Icon'

defineProps({
  items: { type: Array, required: true },
  selected: { type: String, default: null },
  loading: Boolean,
  error: Boolean,
  hasMore: Boolean,
  canCreate: Boolean,
  readyToSend: Boolean,
})
defineEmits(['select', 'retry', 'load-more', 'create'])
</script>
