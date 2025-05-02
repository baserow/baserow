<template>
  <div>
    <div v-if="!loaded && loading" class="loading-absolute-center" />
    <template v-else>
      <div class="row-history">
        <div v-if="entriesWithContents.length > 0">
          <InfiniteScroll
            ref="infiniteScroll"
            :current-count="currentCount"
            :max-count="totalCount"
            :loading="loading"
            :reverse="true"
            :render-end="false"
            @load-next-page="loadNextPage"
          >
            <template #default>
              <div
                v-for="(entry, index) in entriesWithContents"
                :key="entry.id"
              >
                <div
                  v-if="
                    shouldDisplayDateSeparator(
                      entriesWithContents,
                      'timestamp',
                      index
                    )
                  "
                  class="row-history__day-separator"
                >
                  <span>{{ formatDateSeparator(entry.timestamp) }}</span>
                </div>
                <RowHistoryEntry
                  :entry="entry"
                  :workspace-id="database.workspace.id"
                  :fields="fields"
                  :class="{
                    'row-history-entry--first':
                      index === 0 ||
                      shouldDisplayDateSeparator(
                        entriesWithContents,
                        'timestamp',
                        index - 1
                      ),
                  }"
                >
                </RowHistoryEntry>
              </div>
            </template>
          </InfiniteScroll>
        </div>
        <div v-else class="row-history__empty">
          <i class="row-history__empty-icon baserow-icon-history"></i>
          <div class="row-history__empty-text">
            {{ $t('rowHistorySidebar.empty') }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import {
  shouldDisplayDateSeparator,
  formatDateSeparator,
} from '@baserow/modules/database/utils/date'
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import RowHistoryEntry from '@baserow/modules/database/components/row/RowHistoryEntry.vue'

export default {
  name: 'RowHistorySidebar',
  components: {
    InfiniteScroll,
    RowHistoryEntry,
  },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({
      entries: 'rowHistory/getSortedEntries',
      loading: 'rowHistory/getLoading',
      loaded: 'rowHistory/getLoaded',
      currentCount: 'rowHistory/getCurrentCount',
      totalCount: 'rowHistory/getTotalCount',
    }),
    entriesWithContents() {
      const fieldIds = this.fields.map((f) => f.id)

      const entriesToRender = this.entries.filter((entry) => {
        const entryFields = new Set(
          Object.keys(entry.before).concat(Object.keys(entry.after))
        )
        const validEntryFieldIds = entryFields
          .map((fieldIdentifier) => entry.fields_metadata[fieldIdentifier]?.id)
          .filter((entryFieldId) => fieldIds.includes(entryFieldId))
        return (
          validEntryFieldIds.size > 0 || entry.action_type !== 'update_rows'
        )
      })

      return entriesToRender
    },
  },
  watch: {
    row(newRow, oldRow) {
      this.initialLoad()
    },
  },
  async created() {
    await this.initialLoad()
  },
  methods: {
    async initialLoad() {
      try {
        const tableId = this.table.id
        const rowId = this.row.id

        // If the row is not an integer, it can mean that the row hasn't been created
        // in the backend yet. It's fine to not do anything then, because there is no
        // history available anyway.
        if (Number.isInteger(rowId)) {
          await this.$store.dispatch('rowHistory/fetchInitial', {
            tableId,
            rowId,
          })
        }
      } catch (e) {
        notifyIf(e, 'application')
      }
    },
    async loadNextPage() {
      try {
        const tableId = this.table.id
        const rowId = this.row.id
        await this.$store.dispatch('rowHistory/fetchNextPage', {
          tableId,
          rowId,
        })
      } catch (e) {
        notifyIf(e, 'application')
      }
    },
    shouldDisplayDateSeparator,
    formatDateSeparator,
  },
}
</script>
