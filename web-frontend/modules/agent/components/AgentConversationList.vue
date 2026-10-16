<template>
  <aside class="agent-conversations">
    <div class="agent-conversations__header">
      {{ $t('agent.recent') }}
    </div>
    <div class="agent-conversations__content">
      <p
        v-if="!error && !items.length"
        class="agent-conversations__empty"
        role="status"
        aria-live="polite"
      >
        {{
          $t(loading ? 'agent.loadingConversations' : 'agent.noConversations')
        }}
      </p>
      <ul v-if="items.length" class="agent-conversations__list">
        <li v-for="item in items" :key="item.uuid">
          <button
            class="agent-conversations__item"
            :class="{
              'agent-conversations__item--selected': item.uuid === selected,
            }"
            :aria-current="item.uuid === selected ? 'true' : undefined"
            @click="$emit('select', item)"
          >
            <span
              class="agent-conversations__status agent-conversations__status--idle"
              aria-hidden="true"
            />
            <span class="agent-conversations__item-name">{{
              item.title || $t('agent.newConversation')
            }}</span>
            <span v-if="item.local" class="agent-conversations__draft">{{
              $t('agent.draft')
            }}</span>
          </button>
        </li>
      </ul>
      <Alert v-if="error" type="error" class="margin-top-2">
        {{ $t('agent.conversationsLoadError') }}
        <template #actions
          ><Button type="secondary" size="small" @click="$emit('retry')">{{
            $t('action.retry')
          }}</Button></template
        >
      </Alert>
      <Button
        v-else-if="hasMore"
        type="secondary"
        size="small"
        :loading="loading"
        class="agent-conversations__more"
        @click="$emit('load-more')"
        >{{ $t('agent.loadMore') }}</Button
      >
    </div>
    <div v-if="canCreate" class="agent-conversations__footer">
      <Button
        type="secondary"
        icon="iconoir-plus"
        :disabled="!ready"
        @click="$emit('create')"
        >{{ $t('agent.newConversation') }}</Button
      >
    </div>
  </aside>
</template>

<script setup>
defineProps({
  items: { type: Array, required: true },
  selected: { type: String, default: null },
  loading: Boolean,
  error: Boolean,
  hasMore: Boolean,
  canCreate: Boolean,
  ready: Boolean,
})
defineEmits(['select', 'retry', 'load-more', 'create'])
</script>
