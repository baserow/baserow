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
        <li
          v-for="item in items"
          :key="item.uuid"
          class="agent-conversations__row"
          :class="{
            'agent-conversations__row--manageable': hasOptions(item),
            'agent-conversations__row--menu-open': item.uuid === menuUuid,
          }"
        >
          <div
            v-if="item.uuid === renamingUuid"
            class="agent-conversations__item agent-conversations__item--renaming"
          >
            <Icon
              icon="iconoir-chat-bubble"
              type="secondary"
              aria-hidden="true"
            />
            <input
              ref="renameInput"
              v-model="renameTitle"
              class="agent-conversations__rename"
              maxlength="250"
              :aria-label="$t('agent.conversationTitle')"
              @keydown.enter.prevent="finishRename(item)"
              @keydown.esc.prevent="renamingUuid = null"
              @blur="finishRename(item)"
            />
          </div>
          <button
            v-else
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
          <button
            v-if="hasOptions(item) && item.uuid !== renamingUuid"
            type="button"
            class="agent-conversations__options"
            :aria-label="$t('agent.conversationOptions')"
            aria-haspopup="menu"
            :aria-expanded="item.uuid === menuUuid ? 'true' : 'false'"
            @click="toggleMenu($event.currentTarget, item)"
          >
            <i class="baserow-icon-more-vertical" aria-hidden="true"></i>
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
    <Context ref="menu" @hidden="menuUuid = null">
      <ul class="context__menu">
        <li v-if="canUpdate" class="context__menu-item">
          <a class="context__menu-item-link" @click="startRename">
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{ $t('action.rename') }}
          </a>
        </li>
        <li
          v-if="canDelete"
          class="context__menu-item"
          :class="{ 'context__menu-item--with-separator': canUpdate }"
        >
          <a
            class="context__menu-item-link context__menu-link--delete"
            @click="remove"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('action.delete') }}
          </a>
        </li>
      </ul>
    </Context>
  </aside>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import Icon from '@baserow/modules/core/components/Icon'
import Context from '@baserow/modules/core/components/Context'

const props = defineProps({
  items: { type: Array, required: true },
  selected: { type: String, default: null },
  loading: Boolean,
  error: Boolean,
  hasMore: Boolean,
  canCreate: Boolean,
  readyToSend: Boolean,
  canUpdate: Boolean,
  canDelete: Boolean,
})
const emit = defineEmits([
  'select',
  'retry',
  'load-more',
  'create',
  'update',
  'delete',
])

const menu = ref(null)
const menuItem = ref(null)
const menuUuid = ref(null)
const renameInput = ref([])
const renamingUuid = ref(null)
const renameTitle = ref('')

// A draft exists only in this tab until its first message is sent.
const hasOptions = (item) => !item.local && (props.canUpdate || props.canDelete)

function toggleMenu(target, item) {
  const otherItem = menuUuid.value !== item.uuid
  menuItem.value = item
  menuUuid.value = item.uuid
  menu.value.toggle(target, 'bottom', 'right', 4, 0, otherItem || undefined)
}

async function startRename() {
  menu.value.hide()
  renameTitle.value = menuItem.value.title
  renamingUuid.value = menuItem.value.uuid
  await nextTick()
  renameInput.value[0]?.focus()
  renameInput.value[0]?.select()
}

function finishRename(item) {
  if (renamingUuid.value !== item.uuid) return
  renamingUuid.value = null
  const title = renameTitle.value.trim()
  if (title && title !== item.title) emit('update', item, { title })
}

function remove() {
  menu.value.hide()
  emit('delete', menuItem.value)
}
</script>
