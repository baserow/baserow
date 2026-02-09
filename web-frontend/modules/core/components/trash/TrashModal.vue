<template>
  <Modal
    ref="modal"
    :full-height="true"
    :left-sidebar="true"
    :left-sidebar-scrollable="true"
    :content-scrollable="true"
  >
    <template #sidebar>
      <TrashSidebar
        v-if="!loading"
        :workspaces="workspaces"
        :selected-trash-workspace="selectedTrashWorkspace"
        :selected-trash-application="selectedTrashApplication"
        @selected="selectWorkspaceOrApp"
      ></TrashSidebar>
    </template>
    <template #content>
      <div v-if="loading" class="loading-absolute-center"></div>
      <div v-else-if="workspaces.length === 0" class="placeholder">
        <div class="placeholder__icon">
          <i class="iconoir-book-stack"></i>
        </div>
        <h1 class="placeholder__title">{{ $t('trashModal.emptyTitle') }}</h1>
        <p
          v-if="$hasPermission('create_workspace')"
          class="placeholder__content"
        >
          {{ $t('trashModal.emptyMessage') }}
        </p>
        <p v-else class="placeholder__content">
          {{ $t('trashModal.emptyMessageWithoutCreatePermission') }}
        </p>
      </div>
      <TrashContent
        v-else
        :selected-trash-workspace="selectedTrashWorkspace"
        :selected-trash-application="selectedTrashApplication"
        :trash-contents="trashContents"
        :loading-contents="loadingContents"
        :loading-next-page="loadingNextPage"
        :total-server-side-trash-contents-count="
          totalServerSideTrashContentsCount
        "
        @empty="onEmpty"
        @restore="onRestore"
        @load-next-page="loadNextPage"
      ></TrashContent>
    </template>
  </Modal>
</template>

<script>
import { mapState } from 'vuex'

import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import TrashService from '@baserow/modules/core/services/trash'
import TrashSidebar from '@baserow/modules/core/components/trash/TrashSidebar'
import TrashContent from '@baserow/modules/core/components/trash/TrashContents'

export default {
  name: 'TrashModal',
  components: { TrashSidebar, TrashContent },
  mixins: [modal],
  props: {
    initialWorkspace: {
      type: Object,
      required: false,
      default: null,
    },
    initialApplication: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      loading: true,
      loadingContents: true,
      loadingNextPage: false,
      workspaces: [],
      trashContents: [],
      selectedTrashWorkspace: null,
      selectedTrashApplication: null,
      totalServerSideTrashContentsCount: 0,
    }
  },
  computed: {
    ...mapState({
      selectedWorkspace: (state) => state.workspace.selected,
      selectedApplication: (state) => state.application.selected,
    }),
  },
  methods: {
    /**
     * Chooses which workspace to show when the modal is shown.
     **/
    pickInitialWorkspaceToSelect() {
      // The initial or selected workspaces will not contain the trashed flag as they so
      // we must look them up in the workspaces fetched from the trash api.
      const initialWorkspaceWithTrashInfo = this.initialWorkspace
        ? this.workspaces.find((i) => i.id === this.initialWorkspace.id)
        : null
      const selectedWorkspaceWithTrashInfo = this.selectedWorkspace
        ? this.workspaces.find((i) => i.id === this.selectedWorkspace.id)
        : null
      return (
        initialWorkspaceWithTrashInfo ||
        selectedWorkspaceWithTrashInfo ||
        this.workspaces[0] || // When all workspaces are trashed we want to pick the first one.
        null
      )
    },
    /**
     * Chooses which app to show when the modal is shown.
     **/
    pickInitialApplicationToSelect(firstWorkspaceToShow) {
      if (firstWorkspaceToShow === null) {
        return null
      } else {
        // The initial or selected apps will not contain the trashed flag as they so
        // we must look them up in the workspaces fetched from the trash api.
        const applications = firstWorkspaceToShow.applications
        if (this.initialApplication || this.initialWorkspace) {
          // When either of the initial props are set we have been opened via a context
          // menu shortcut.
          return this.initialApplication
            ? applications.find((i) => i.id === this.initialApplication.id)
            : null
        } else {
          return this.selectedApplication
            ? applications.find((i) => i.id === this.selectedApplication.id)
            : null
        }
      }
    },
    /**
     * Loads the structure of the trash modal from the server, selects an initial
     * workspace or application depending on the props and shows the trash modal.
     **/
    async show(...args) {
      modal.methods.show.call(this, ...args)

      this.loading = true
      this.workspaces = []
      this.selectedTrashWorkspace = null
      this.selectedTrashApplication = null

      try {
        const { data } = await TrashService(this.$client).fetchStructure()
        this.workspaces = data.workspaces
        const initialWorkspace = this.pickInitialWorkspaceToSelect()
        await this.selectWorkspaceOrApp({
          workspace: initialWorkspace,
          application: this.pickInitialApplicationToSelect(initialWorkspace),
        })
      } catch (error) {
        notifyIf(error, 'trash')
        this.hide()
      }
      this.loading = false
    },
    /**
     * Loads the next page of trash contents for the currently selected application.
     */
    async loadTrashContentsPage(nextPage) {
      if (
        this.selectedTrashWorkspace === null &&
        this.selectedTrashApplication === null
      ) {
        return
      }
      try {
        const { data } = await TrashService(this.$client).fetchContents({
          page: nextPage,
          workspaceId: this.selectedTrashWorkspace.id,
          applicationId:
            this.selectedTrashApplication !== null
              ? this.selectedTrashApplication.id
              : null,
        })
        this.totalServerSideTrashContentsCount = data.count
        data.results.forEach((entry) => {
          entry.loading = false
          this.trashContents.push(entry)
        })
      } catch (error) {
        notifyIf(error, 'trash')
      }
    },
    /**
     * Switches to a different workspace or application to display the trash contents for
     * and triggers the fetch for the first page of contents.
     */
    async selectWorkspaceOrApp({ workspace, application = null }) {
      this.selectedTrashWorkspace = workspace
      this.selectedTrashApplication = application
      this.loadingContents = true
      this.trashContents = []
      this.totalServerSideTrashContentsCount = 0
      await this.loadTrashContentsPage(1)
      this.loadingContents = false
    },
    /**
     * Loads another page of contents in after we have already loaded the initial
     * page of contents, hence we want to use a different loading indicator as it is
     * ok to say, restore an item whilst we are loading in another page.
     */
    async loadNextPage(nextPage) {
      this.loadingNextPage = true
      await this.loadTrashContentsPage(nextPage)
      this.loadingNextPage = false
    },
    /**
     * Triggered when a user requests a trashEntry be restored. Sends the request to
     * the server, updates the client side state if successful and updates the trash
     * structure if say a workspace or application was restored.
     */
    async onRestore(trashEntry) {
      try {
        trashEntry.loading = true
        await TrashService(this.$client).restore({
          trash_item_type: trashEntry.trash_item_type,
          trash_item_id: trashEntry.trash_item_id,
          parent_trash_item_id: trashEntry.parent_trash_item_id,
        })
        const index = this.trashContents.findIndex(
          (t) => t.id === trashEntry.id
        )
        this.trashContents.splice(index, 1)
        this.totalServerSideTrashContentsCount--
        this.updateStructureIfWorkspaceOrAppRestored(trashEntry)
      } catch (error) {
        notifyIf(error, 'trash')
      }
      trashEntry.loading = false
    },
    updateStructureIfWorkspaceOrAppRestored(trashEntry) {
      /**
       * If a workspace or app is trashed it is displayed with a strike through it's text.
       * This method checks if a restored trash entry is a workspace or application and
       * if so updates the state of said workspace/app so it no longer is displayed as
       * trashed.
       */
      const trashItemId = trashEntry.trash_item_id
      const trashItemType = trashEntry.trash_item_type
      if (trashItemType === 'workspace') {
        const index = this.workspaces.findIndex(
          (workspace) => workspace.id === trashItemId
        )
        this.workspaces[index].trashed = false
      } else if (trashItemType === 'application') {
        const index = this.selectedTrashWorkspace.applications.findIndex(
          (app) => app.id === trashItemId
        )
        this.selectedTrashWorkspace.applications[index].trashed = false
      }
    },
    /**
     * Triggered when the user has requested the currently selected workspace or app
     * should be emptied. If the selected item is trashed itself the empty operation
     * will permanently delete the selected item also. Once emptied this method will
     * ensure that any now permanently deleted workspaces or apps are removed from the
     * sidebar.
     */
    async onEmpty() {
      this.loadingContents = true
      try {
        const applicationIdOrNull =
          this.selectedTrashApplication !== null
            ? this.selectedTrashApplication.id
            : null
        await TrashService(this.$client).emptyContents({
          workspaceId: this.selectedTrashWorkspace.id,
          applicationId: applicationIdOrNull,
        })
        this.removeWorkspaceOrAppFromSidebarIfNowPermDeleted()
        this.trashContents = []
        this.totalServerSideTrashContentsCount = 0
      } catch (error) {
        notifyIf(error, 'trash')
      }
      this.loadingContents = false
    },
    removeSelectedAppFromSidebar() {
      const applicationId = this.selectedTrashApplication.id

      const indexToDelete = this.selectedTrashWorkspace.applications.findIndex(
        (app) => app.id === applicationId
      )
      this.selectedTrashWorkspace.applications.splice(indexToDelete, 1)
      if (this.selectedTrashWorkspace.applications.length > 0) {
        this.selectedTrashApplication =
          this.selectedTrashWorkspace.applications[0]
      } else {
        this.selectedTrashApplication = null
      }
    },
    removeSelectedTrashWorkspaceFromSidebar() {
      const indexToDelete = this.workspaces.findIndex(
        (workspace) => workspace.id === this.selectedTrashWorkspace.id
      )
      this.workspaces.splice(indexToDelete, 1)
      if (this.workspaces.length > 0) {
        this.selectedTrashWorkspace = this.workspaces[0]
      } else {
        this.selectedTrashWorkspace = null
      }
    },
    /**
     * Updates the trash structure to remove any deleted workspaces or applications after
     * an empty is performed.
     */
    removeWorkspaceOrAppFromSidebarIfNowPermDeleted() {
      if (
        this.selectedTrashApplication !== null &&
        this.selectedTrashApplication.trashed
      ) {
        this.removeSelectedAppFromSidebar()
        this.selectWorkspaceOrApp({
          workspace: this.selectedTrashWorkspace,
          application: this.selectedTrashApplication,
        })
      } else if (this.selectedTrashWorkspace.trashed) {
        this.removeSelectedTrashWorkspaceFromSidebar()
        this.selectWorkspaceOrApp({
          workspace: this.selectedTrashWorkspace,
          application: this.selectedTrashApplication,
        })
      } else if (this.selectedTrashApplication === null) {
        // The workspace was emptied, it might have contained trashed applications hence
        // we need to search through the trash and remove any now deleted applications.
        for (const app of this.selectedTrashWorkspace.applications.slice()) {
          if (app.trashed) {
            const index = this.selectedTrashWorkspace.applications.findIndex(
              (i) => i.id === app.id
            )
            this.selectedTrashWorkspace.applications.splice(index, 1)
          }
        }
      }
    },
  },
}
</script>
