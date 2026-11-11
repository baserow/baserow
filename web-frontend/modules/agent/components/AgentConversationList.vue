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
      <ul v-if="shownItems.length" class="agent-conversations__list">
        <li
          v-for="item in shownItems"
          :key="item.uuid"
          class="agent-conversations__row"
          :class="{
            'agent-conversations__row--manageable': hasOptions(item),
            'agent-conversations__row--menu-open': item.uuid === menuItem?.uuid,
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
              @keydown.enter="confirmRename($event, item)"
              @keydown.esc.prevent="cancelRename(item)"
              @blur="finishRename(item)"
            />
          </div>
          <button
            v-else
            :ref="(element) => setItemButton(item.uuid, element)"
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
              v-if="item.pending_approval_count > 0"
              class="agent-conversations__status-label"
              >{{ $t('agent.waitingForApproval') }}</span
            >
            <span
              class="agent-conversations__status"
              :class="statusClass(item)"
              aria-hidden="true"
            />
          </button>
          <button
            v-if="hasOptions(item) && item.uuid !== renamingUuid"
            type="button"
            class="agent-conversations__options"
            :aria-label="$t('agent.conversationOptions')"
            aria-haspopup="menu"
            :aria-expanded="item.uuid === menuItem?.uuid ? 'true' : 'false'"
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
    <Context ref="menu" @hidden="menuItem = null">
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
            class="context__menu-item-link context__menu-item-link--delete"
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
import { nextTick, ref, watch } from 'vue'
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
const renameInput = ref([])
const renamingUuid = ref(null)
const renameTitle = ref('')
// Chrome blurs a focused input that the list moves, which would end the rename.
const shownItems = ref(props.items)
const itemButtons = {}
let renameOriginal = ''

// A draft exists only in this tab until its first message is sent.
const hasOptions = (item) => !item.local && (props.canUpdate || props.canDelete)
const isListed = (uuid) => props.items.some((item) => item.uuid === uuid)

watch([() => props.items, renamingUuid], ([items, renaming]) => {
  if (!renaming) shownItems.value = items
})

// Another session can delete the conversation whose menu or rename is open.
watch(
  () => props.items,
  () => {
    if (menuItem.value && !isListed(menuItem.value.uuid)) menu.value.hide()
    if (renamingUuid.value && !isListed(renamingUuid.value)) {
      renamingUuid.value = null
    }
  }
)

function setItemButton(uuid, element) {
  if (element) itemButtons[uuid] = element
  else delete itemButtons[uuid]
}

function statusClass(item) {
  if (item.pending_approval_count > 0) {
    return 'agent-conversations__status--waiting'
  }
  return item.run_id
    ? 'agent-conversations__status--replying'
    : 'agent-conversations__status--idle'
}

function toggleMenu(target, item) {
  if (menuItem.value?.uuid === item.uuid) return menu.value.hide()
  menuItem.value = item
  menu.value.show(target, 'bottom', 'right', 4)
}

async function startRename() {
  const item = menuItem.value
  menu.value.hide()
  renameOriginal = item.title
  renameTitle.value = item.title
  renamingUuid.value = item.uuid
  await nextTick()
  renameInput.value[0]?.focus()
  renameInput.value[0]?.select()
}

function finishRename(item) {
  if (renamingUuid.value !== item.uuid || !isListed(item.uuid)) return
  renamingUuid.value = null
  const title = renameTitle.value.trim()
  if (title && title !== renameOriginal) emit('update', item, { title })
}

async function confirmRename(event, item) {
  // Enter also confirms an input method's composition.
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  finishRename(item)
  await nextTick()
  itemButtons[item.uuid]?.focus()
}

async function cancelRename(item) {
  renamingUuid.value = null
  await nextTick()
  itemButtons[item.uuid]?.focus()
}

function remove() {
  const item = menuItem.value
  menu.value.hide()
  emit('delete', item)
}
</script>
