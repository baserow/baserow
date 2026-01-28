<template>
  <div>
    <div class="trash__title">
      <div class="trash__title-left">
        <h2 class="trash__title-heading">{{ title }}</h2>
        <div class="trash__title-description">
          {{ $t('trashContents.message', { duration: trashDuration }) }}
        </div>
      </div>
      <div class="trash__title-right">
        <Button
          v-show="totalServerSideTrashContentsCount > 0 && !parentIsTrashed"
          type="danger"
          :loading="loadingContents"
          :disabled="loadingContents"
          @click="showEmptyModalIfNotLoading"
        >
          {{ emptyButtonText }}</Button
        >
      </div>
    </div>
    <div v-if="loadingContents" class="loading-overlay"></div>
    <div
      v-else-if="totalServerSideTrashContentsCount === 0"
      class="trash__empty"
    >
      <i class="trash__empty-icon iconoir-refresh-double"></i>
      <div class="trash__empty-text">
        {{ $t('trashContents.empty') }}
      </div>
    </div>
    <div v-else class="trash__entries">
      <InfiniteScroll
        :max-count="totalServerSideTrashContentsCount"
        :current-count="trashContents.length"
        :loading="loadingNextPage"
        @load-next-page="$emit('load-next-page', $event)"
      >
        <template #default>
          <TrashEntry
            v-for="item in trashContents"
            :key="'trash-item-' + item.id"
            :trash-entry="item"
            :disabled="loadingContents || shouldTrashEntryBeDisabled(item)"
            @restore="$emit('restore', $event)"
          ></TrashEntry>
        </template>
        <template #end> <div class="trash__end-line"></div> </template>
      </InfiniteScroll>
    </div>
    <TrashEmptyModal
      ref="emptyModal"
      :name="title"
      :loading="loadingContents"
      :selected-is-trashed="selectedItem.trashed"
      @empty="$emit('empty')"
    ></TrashEmptyModal>
  </div>
</template>

<script>
/**
 * Displays a infinite scrolling list of trash contents for either a selectedTrashWorkspace or
 * a specific selectedTrashApplication in the selectedTrashWorkspace. The user can empty the trash
 * contents permanently deleting them all, or restore individual trashed items.
 *
 * If the selectedItem (the selectedTrashApplication if provided, otherwise the selectedTrashWorkspace
 * ) is trashed itself then the modal will display buttons and modals which indicate
 * that they will permanently delete the selectedItem instead of just emptying it's
 * contents.
 */

import moment from '@baserow/modules/core/moment'
import TrashEntry from '@baserow/modules/core/components/trash/TrashEntry'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import TrashEmptyModal from '@baserow/modules/core/components/trash/TrashEmptyModal'

export default {
  name: 'TrashContents',
  components: { InfiniteScroll, TrashEntry, TrashEmptyModal },
  mixins: [],
  props: {
    selectedTrashWorkspace: {
      type: Object,
      required: true,
    },
    selectedTrashApplication: {
      type: Object,
      required: false,
      default: null,
    },
    trashContents: {
      type: Array,
      required: true,
    },
    loadingContents: {
      type: Boolean,
      required: true,
    },
    loadingNextPage: {
      type: Boolean,
      required: true,
    },
    totalServerSideTrashContentsCount: {
      type: Number,
      required: true,
    },
  },
  emits: ['empty', 'load-next-page', 'restore'],
  computed: {
    parentIsTrashed() {
      return (
        this.selectedTrashApplication !== null &&
        this.selectedTrashWorkspace.trashed
      )
    },
    selectedItem() {
      return this.selectedTrashApplication === null
        ? this.selectedTrashWorkspace
        : this.selectedTrashApplication
    },
    selectedItemType() {
      return this.selectedTrashApplication === null
        ? 'workspace'
        : 'application'
    },
    title() {
      const title = this.selectedItem.name
      return title === ''
        ? this.$t('trashContents.unnamed', {
            type: this.$t('trashType.' + this.selectedItemType),
            id: this.selectedItem.id,
          })
        : title
    },
    emptyButtonText() {
      if (this.selectedItem.trashed) {
        return this.$t('trashContents.emptyButtonTrashed', {
          type: this.$t('trashType.' + this.selectedItemType),
        })
      } else {
        return this.$t('trashContents.emptyButtonNotTrashed', {
          type: this.$t('trashType.' + this.selectedItemType),
        })
      }
    },
    trashDuration() {
      const hours = this.$config.public.hoursUntilTrashPermanentlyDeleted
      return moment().subtract(hours, 'hours').fromNow(true)
    },
  },
  methods: {
    showEmptyModalIfNotLoading() {
      if (!this.loadingContents) {
        this.$refs.emptyModal.show()
      }
    },
    shouldTrashEntryBeDisabled(entry) {
      const entryIsForSelectedItem =
        entry.trash_item_id === this.selectedItem.id &&
        entry.trash_item_type === this.selectedItemType
      return (
        this.parentIsTrashed ||
        (this.selectedItem.trashed && !entryIsForSelectedItem)
      )
    },
  },
}
</script>
