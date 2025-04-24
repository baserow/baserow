<template>
  <div>
    <template v-if="!hasPremiumFeaturesEnabled">
      <div class="row-comments">
        <div class="row-comments__empty">
          <i class="row-comments__empty-icon iconoir-multi-bubble"></i>
          <div class="row-comments__empty-text">
            {{ $t('rowCommentSidebar.onlyPremium') }}
          </div>
          <Button
            type="primary"
            icon="iconoir-no-lock"
            @click="$refs.paidFeaturesModal.show()"
          >
            {{ $t('rowCommentSidebar.more') }}
          </Button>
        </div>
        <PaidFeaturesModal
          ref="paidFeaturesModal"
          initial-selected-type="row_comments"
          :workspace="workspace"
        ></PaidFeaturesModal>
      </div>
    </template>
    <template v-else>
      <div v-if="!loaded && loading" class="loading-absolute-center" />
      <div v-else>
        <div class="row-comments">
          <div v-if="currentCount === 0" class="row-comments__empty">
            <i class="row-comments__empty-icon iconoir-multi-bubble"></i>
            <div class="row-comments__empty-text">
              <template
                v-if="
                  !$hasPermission(
                    'database.table.create_comment',
                    table,
                    workspace.id
                  )
                "
                >{{ $t('rowCommentSidebar.readOnlyNoComment') }}</template
              >
              <template v-else>
                {{ $t('rowCommentSidebar.noComment') }}
              </template>
            </div>
          </div>
          <div v-else class="row-comments__body">
            <InfiniteScroll
              ref="infiniteScroll"
              :current-count="currentCount"
              :max-count="totalCount"
              :loading="loading"
              :reverse="true"
              :render-end="false"
              @load-next-page="nextPage"
            >
              <template #default>
                <div
                  v-for="(c, index) in comments"
                  :key="'row-comment-' + c.id"
                >
                  <div
                    v-if="
                      shouldDisplayDateSeparator(comments, 'created_on', index)
                    "
                    class="row-comment__day-separator"
                  >
                    <span>{{ formatDateSeparator(c.created_on) }}</span>
                  </div>
                  <RowComment
                    :comment="c"
                    :workspace="workspace"
                    :can-edit="canEditComments"
                    :can-delete="canDeleteComments"
                  />
                </div>
              </template>
            </InfiniteScroll>
          </div>
          <div
            v-if="
              $hasPermission(
                'database.table.create_comment',
                table,
                workspace.id
              )
            "
            class="row-comments__foot"
          >
            <RichTextEditor
              v-model="comment"
              editor-class="rich-text-editor__content--comment"
              :mentionable-users="workspace.users"
              :placeholder="$t('rowCommentSidebar.comment')"
              :enter-stop-edit="true"
              @stop-edit="postComment()"
            />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import {
  shouldDisplayDateSeparator,
  formatDateSeparator,
} from '@baserow/modules/database/utils/date'
import { notifyIf } from '@baserow/modules/core/utils/error'
import RowComment from '@baserow_premium/components/row_comments/RowComment'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'RowCommentsSidebar',
  components: {
    PaidFeaturesModal,
    InfiniteScroll,
    RowComment,
    RichTextEditor,
  },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      required: true,
      type: Object,
    },
    row: {
      required: true,
      type: Object,
    },
  },
  data() {
    return {
      comment: '',
    }
  },
  computed: {
    hasPremiumFeaturesEnabled() {
      return this.$hasFeature(
        PremiumFeatures.PREMIUM,
        this.database.workspace.id
      )
    },
    ...mapGetters({
      loggedUserId: 'auth/getUserId',
      comments: 'row_comments/getSortedRowComments',
      loading: 'row_comments/getLoading',
      loaded: 'row_comments/getLoaded',
      currentCount: 'row_comments/getCurrentCount',
      totalCount: 'row_comments/getTotalCount',
      additionalUserData: 'auth/getAdditionalUserData',
    }),
    canEditComments() {
      return this.$hasPermission(
        'database.table.update_comment',
        this.table,
        this.database.workspace.id
      )
    },
    canDeleteComments() {
      return this.$hasPermission(
        'database.table.delete_comment',
        this.table,
        this.database.workspace.id
      )
    },
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
  },
  watch: {
    async hasPremiumFeaturesEnabled() {
      await this.initialLoad()
    },
    'row.id': {
      handler() {
        this.initialLoad()
      },
    },
  },
  async created() {
    await this.initialLoad()
  },
  methods: {
    async initialLoad() {
      if (!this.hasPremiumFeaturesEnabled) {
        return
      }

      try {
        const tableId = this.table.id
        const rowId = this.row.id

        // If the row is not an integer, it can mean that the row hasn't been created
        // in the backend yet. It's fine to not do anything then, because there are no
        // comments anyway.
        if (Number.isInteger(rowId)) {
          await this.$store.dispatch('row_comments/fetchRowComments', {
            tableId,
            rowId,
          })
        }
      } catch (e) {
        notifyIf(e, 'application')
      }
    },
    async postComment() {
      const comment = this.comment
      if (
        !comment ||
        !this.$hasPermission(
          'database.table.create_comment',
          this.table,
          this.database.workspace.id
        )
      ) {
        return
      }
      try {
        this.comment = ''
        await this.$store.dispatch('row_comments/postComment', {
          tableId: this.table.id,
          rowId: this.row.id,
          message: comment,
        })
        this.$refs.infiniteScroll.scrollToStart()
      } catch (e) {
        notifyIf(e, 'application')
      }
    },
    async nextPage() {
      try {
        await this.$store.dispatch('row_comments/fetchNextSetOfComments', {
          tableId: this.table.id,
          rowId: this.row.id,
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
