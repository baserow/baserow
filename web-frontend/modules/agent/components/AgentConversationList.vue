<template>
  <aside class="agent-conversations" :aria-busy="loading">
    <Dropdown
      class="agent-conversations__filter"
      :model-value="filter"
      :show-search="false"
      :aria-label="$t('agent.filterConversations')"
      @update:model-value="$emit('filter', $event)"
    >
      <DropdownItem
        value="all"
        :name="$t('agent.allConversations')"
        icon="iconoir-filter-list"
      />
      <DropdownItem
        value="waiting"
        :name="$t('agent.waiting')"
        icon="iconoir-clock"
      />
      <DropdownItem
        value="failed"
        :name="$t('agent.failed')"
        icon="iconoir-warning-circle"
      />
      <DropdownItem
        value="pinned"
        :name="$t('agent.pinned')"
        icon="iconoir-pin"
      />
      <DropdownItem
        value="triggered"
        :name="$t('agent.triggered')"
        icon="iconoir-flash"
      />
      <DropdownItem
        value="private"
        :name="$t('agent.private')"
        icon="iconoir-lock"
      />
      <DropdownItem
        value="shared"
        :name="$t('agent.shared')"
        icon="iconoir-community"
      />
    </Dropdown>
    <InfiniteScroll
      ref="scroll"
      class="agent-conversations__content"
      :current-count="items.length"
      :has-more-page="hasMore && !error"
      :loading="loading"
      :render-end="false"
      fill
      @load-next-page="$emit('load-more')"
    >
      <div class="agent-conversations__header">
        {{
          $t(
            shownItems[0]?.pinned || filter === 'pinned'
              ? 'agent.pinned'
              : 'agent.recent'
          )
        }}
      </div>
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
        <template v-for="(item, index) in shownItems" :key="item.uuid">
          <li
            v-if="index > 0 && shownItems[index - 1].pinned && !item.pinned"
            class="agent-conversations__header"
          >
            {{ $t('agent.recent') }}
          </li>
          <li
            class="agent-conversations__row"
            :class="{
              'agent-conversations__row--manageable': hasOptions(item),
              'agent-conversations__row--menu-open':
                item.uuid === menuItem?.uuid,
            }"
          >
            <div
              v-if="item.uuid === renamingUuid"
              class="agent-conversations__item agent-conversations__item--renaming"
            >
              <Icon
                :icon="conversationIcon(item)"
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
              <span class="agent-conversations__origin">
                <Icon
                  :icon="conversationIcon(item)"
                  type="secondary"
                  aria-hidden="true"
                />
                <span
                  v-if="hasStatus(item)"
                  class="agent-conversations__status"
                  :class="`agent-conversations__status--${status(item)}`"
                  aria-hidden="true"
                ></span>
              </span>
              <span class="agent-conversations__text">
                <span class="agent-conversations__title">
                  <span
                    class="agent-conversations__item-name"
                    :title="item.title"
                    >{{ item.title || $t('agent.newConversation') }}</span
                  >
                  <span
                    v-if="!item.shared"
                    class="agent-conversations__private"
                    role="img"
                    :aria-label="$t('agent.privateConversation')"
                    :title="$t('agent.privateConversation')"
                    ><i class="iconoir-lock" aria-hidden="true"></i
                  ></span>
                </span>
                <span class="agent-conversations__meta">
                  <span
                    v-if="hasStatus(item)"
                    class="agent-conversations__status-label"
                    >{{ $t(`agent.${status(item)}`) }}</span
                  >
                  <span v-else class="agent-conversations__detail">{{
                    startedBy(item)
                  }}</span>
                  <span v-if="item.local" class="agent-conversations__draft">{{
                    $t('agent.draft')
                  }}</span>
                  <time
                    v-else-if="item.updated_on"
                    class="agent-conversations__age"
                    :datetime="item.updated_on"
                    >{{
                      getHumanAgoLabel(t, item.updated_on, now ?? undefined)
                    }}</time
                  >
                </span>
              </span>
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
        </template>
      </ul>
      <p v-else-if="!loading && !error" class="agent-conversations__empty">
        {{
          $t(
            filter === 'all'
              ? 'agent.noConversations'
              : 'agent.noMatchingConversations'
          )
        }}
      </p>
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
    </InfiniteScroll>
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
      <ul v-if="menuItem" class="context__menu">
        <li
          v-if="canUpdateItem(menuItem) && !menuItem.shared"
          class="context__menu-item"
        >
          <a class="context__menu-item-link" @click="share">
            <i class="context__menu-item-icon iconoir-community"></i>
            {{ $t('agent.share') }}
          </a>
        </li>
        <li v-if="canUpdateItem(menuItem)" class="context__menu-item">
          <a class="context__menu-item-link" @click="togglePin">
            <i class="context__menu-item-icon iconoir-pin"></i>
            {{ $t(menuItem?.pinned ? 'agent.unpin' : 'agent.pin') }}
          </a>
        </li>
        <li v-if="canUpdateItem(menuItem)" class="context__menu-item">
          <a class="context__menu-item-link" @click="startRename">
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{ $t('action.rename') }}
          </a>
        </li>
        <li
          v-if="canDeleteItem(menuItem)"
          class="context__menu-item"
          :class="{
            'context__menu-item--with-separator': canUpdateItem(menuItem),
          }"
        >
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            @click="remove"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('action.delete') }}
          </a>
        </li>
        <li v-if="canLeaveItem(menuItem)" class="context__menu-item">
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            @click="leave"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('agent.deleteForMe') }}
          </a>
        </li>
      </ul>
    </Context>
    <AgentShareConversationModal
      ref="shareModal"
      @share="$emit('share', $event)"
    />
    <AgentDeleteConversationModal
      ref="deleteModal"
      @leave="$emit('leave', $event)"
      @delete="$emit('delete', $event)"
    />
  </aside>
</template>

<script setup>
import { inject, nextTick, ref, watch } from 'vue'
import { useStore } from 'vuex'
import Icon from '@baserow/modules/core/components/Icon'
import Context from '@baserow/modules/core/components/Context'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import AgentShareConversationModal from '@baserow/modules/agent/components/AgentShareConversationModal'
import { useI18n } from 'vue-i18n'
import AgentDeleteConversationModal from '@baserow/modules/agent/components/AgentDeleteConversationModal'
import { managesConversation } from '@baserow/modules/agent/utils/conversations'
import { useNuxtApp } from '#app'
import { getHumanAgoLabel } from '@baserow/modules/core/utils/date'
import { injectNow } from '@baserow/modules/core/composables/useNow'
import { serviceTypeOf } from '@baserow/modules/agent/utils/triggers'

const props = defineProps({
  items: { type: Array, required: true },
  filter: { type: String, default: 'all' },
  selected: { type: String, default: null },
  loading: Boolean,
  error: Boolean,
  hasMore: Boolean,
  canCreate: Boolean,
  readyToSend: Boolean,
  canUpdate: Boolean,
  canDelete: Boolean,
  /** Whether the viewer may update the agent, which shared conversations require. */
  canUpdateAgent: Boolean,
})
const emit = defineEmits([
  'select',
  'filter',
  'retry',
  'load-more',
  'create',
  'update',
  'share',
  'leave',
  'delete',
])

const { $registry } = useNuxtApp()
const { t } = useI18n()
const store = useStore()
const now = injectNow()
const templatePreview = inject('agentTemplatePreview', false)

const scroll = ref(null)
const menu = ref(null)
const menuItem = ref(null)
const shareModal = ref(null)
const deleteModal = ref(null)
const renameInput = ref([])
const renamingUuid = ref(null)
const renameTitle = ref('')
// Chrome blurs a focused input that the list moves, which would end the rename.
const shownItems = ref(props.items)
const itemButtons = {}
let renameOriginal = ''

function conversationIcon(item) {
  return (
    serviceTypeOf($registry, item.trigger_type)?.icon || 'iconoir-chat-bubble'
  )
}

/** The trigger or the person that started the conversation, by name. */
function startedBy(item) {
  if (item.started_by_trigger) {
    return (
      item.trigger_name ||
      serviceTypeOf($registry, item.trigger_type)?.name ||
      t('agent.startedByTrigger')
    )
  }
  if (!item.owner) {
    if (!item.shared) return ''
    // The examples of a template never had an owner here.
    return t(
      templatePreview ? 'agent.templatePreviewExample' : 'agent.deletedSender'
    )
  }
  return item.owner.id === store.getters['auth/getUserId']
    ? t('agent.you')
    : item.owner.name
}
const managesItem = (item) =>
  managesConversation(
    item,
    store.getters['auth/getUserId'],
    props.canUpdateAgent
  )
const canUpdateItem = (item) => props.canUpdate && managesItem(item)
const canDeleteItem = (item) => props.canDelete && managesItem(item)
// Those asked to approve may only remove it from their own list.
const canLeaveItem = (item) =>
  props.canDelete && !item.shared && !managesItem(item)
// A draft exists only in this tab until its first message is sent.
const hasOptions = (item) =>
  !item.local &&
  (canUpdateItem(item) || canDeleteItem(item) || canLeaveItem(item))
const isListed = (uuid) => props.items.some((item) => item.uuid === uuid)

watch([() => props.items, renamingUuid], ([items, renaming]) => {
  if (!renaming) shownItems.value = items
})

watch(
  () => props.filter,
  () => {
    if (scroll.value) scroll.value.$el.scrollTop = 0
    menu.value?.hide()
    renamingUuid.value = null
  }
)

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

function status(item) {
  if (item.pending_approval_count > 0) return 'waiting'
  if (item.run_id) return 'replying'
  return item.last_reply_failed ? 'failed' : null
}

function hasStatus(item) {
  return status(item) !== null
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

function togglePin() {
  const item = menuItem.value
  menu.value.hide()
  emit('update', item, { pinned: !item.pinned })
}

function share() {
  const item = menuItem.value
  menu.value.hide()
  shareModal.value.show(item)
}

function remove() {
  const item = menuItem.value
  menu.value.hide()
  if (!item.shared && item.participants.length > 1) deleteModal.value.show(item)
  else emit('delete', item)
}

function leave() {
  const item = menuItem.value
  menu.value.hide()
  deleteModal.value.show(item, { forEveryone: false })
}
</script>
