<template>
  <Modal
    ref="modal"
    class="templates-modal"
    :full-screen="true"
    :close-button="false"
    keep-content
    @show="open = true"
    @hidden="hidden"
  >
    <div v-if="loading" class="loading-absolute-center"></div>
    <template v-else>
      <!-- Keyed by the template only, so that the chosen workspace is kept when a
      new revision is shown. The preview loads its content then. -->
      <TemplateDetails
        v-if="selectedTemplate !== null"
        :key="selectedTemplate.id"
        :template="selectedTemplate"
        :categories="selectedTemplateCategories"
        :workspace="workspace"
        :owner-actions="selectedOwnerActions"
        show-back
        class="templates__body"
        @back="selectTemplate(null)"
        @installed="hide()"
        @outdated="templateOutdated"
        @edit="openUpdateModal(selectedTemplate, $event)"
        @delete="openDeleteModal"
        @make-public="openMakePublicModal"
        @make-private="makePrivate"
        @moderated="moderated"
      ></TemplateDetails>
      <TemplateList
        v-show="selectedTemplate === null && tab === 'official'"
        :categories="categories"
        :active="open && selectedTemplate === null && tab === 'official'"
        class="templates__body"
        @selected="selectTemplate"
      >
        <template v-if="showTabs" #head>
          <SegmentControl
            :segments="tabs"
            :active-index="tabIndex"
            type="pills"
            @update:active-index="selectTab(tabs[$event].value)"
          ></SegmentControl>
        </template>
      </TemplateList>
      <!-- Mounted only while its tab is open, so that it's loaded again with the
      changes made in "Your templates". -->
      <PublicTemplateList
        v-if="showTabs && tab === 'public'"
        v-show="selectedTemplate === null"
        ref="publicTemplateList"
        :active="open && selectedTemplate === null"
        :initial-search="sharedSearch"
        class="templates__body"
        @selected="selectPublicTemplate"
      >
        <template #head>
          <SegmentControl
            :segments="tabs"
            :active-index="tabIndex"
            type="pills"
            @update:active-index="selectTab(tabs[$event].value)"
          ></SegmentControl>
        </template>
      </PublicTemplateList>
      <UserTemplateList
        v-if="showTabs && userTemplatesOpened"
        v-show="selectedTemplate === null && tab === 'own'"
        ref="userTemplateList"
        :active="
          open &&
          selectedTemplate === null &&
          tab === 'own' &&
          !creating &&
          !updating &&
          !deleting &&
          !makingPublic
        "
        class="templates__body"
        @selected="selectTemplate($event, true)"
        @create="openCreateModal"
        @edit="openUpdateModal"
        @delete="openDeleteModal"
        @make-public="openMakePublicModal"
        @make-private="makePrivate"
      >
        <template #head>
          <SegmentControl
            :segments="tabs"
            :active-index="tabIndex"
            type="pills"
            @update:active-index="selectTab(tabs[$event].value)"
          ></SegmentControl>
        </template>
      </UserTemplateList>
      <div class="modal__actions">
        <a class="modal__close" @click="hide()">
          <i class="iconoir-cancel"></i>
        </a>
      </div>
    </template>
    <!-- Outside of the loaded content, so that a running job stays monitored
    when the modal is shown again. -->
    <CreateUserTemplateModal
      v-if="showTabs"
      ref="createUserTemplateModal"
      :categories="categories"
      @hidden="creating = false"
      @created="templateCreated"
    ></CreateUserTemplateModal>
    <UpdateUserTemplateModal
      v-if="showTabs && updatedTemplate !== null"
      :key="updatedTemplate.id"
      ref="updateUserTemplateModal"
      :template="updatedTemplate"
      :mode="updateMode"
      :categories="categories"
      @hidden="updating = false"
      @updated="templateUpdated"
      @visibility-changed="templateChanged"
    ></UpdateUserTemplateModal>
    <!-- Not keyed, so that a running deletion is still handled after the modal
    is opened for another template. -->
    <DeleteUserTemplateModal
      v-if="showTabs && deletedTemplate !== null"
      ref="deleteUserTemplateModal"
      :template="deletedTemplate"
      @hidden="deleting = false"
      @deleted="templateDeleted"
    ></DeleteUserTemplateModal>
    <!-- Not keyed, so that a running request is still handled after the modal is
    opened for another template. -->
    <MakeTemplatePublicModal
      v-if="showTabs && madePublicTemplate !== null"
      ref="makeTemplatePublicModal"
      :template="madePublicTemplate"
      @hidden="makingPublic = false"
      @made-public="templateChanged"
    ></MakeTemplatePublicModal>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import { isOwnTemplate } from '@baserow/modules/core/utils/userTemplate'

import CreateUserTemplateModal from '@baserow/modules/core/components/template/CreateUserTemplateModal'
import DeleteUserTemplateModal from '@baserow/modules/core/components/template/DeleteUserTemplateModal'
import MakeTemplatePublicModal from '@baserow/modules/core/components/template/MakeTemplatePublicModal'
import PublicTemplateList from '@baserow/modules/core/components/template/PublicTemplateList'
import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'
import TemplateList from '@baserow/modules/core/components/template/TemplateList'
import UpdateUserTemplateModal from '@baserow/modules/core/components/template/UpdateUserTemplateModal'
import UserTemplateList from '@baserow/modules/core/components/template/UserTemplateList'

export default {
  name: 'TemplateModal',
  components: {
    CreateUserTemplateModal,
    DeleteUserTemplateModal,
    MakeTemplatePublicModal,
    PublicTemplateList,
    TemplateDetails,
    TemplateList,
    UpdateUserTemplateModal,
    UserTemplateList,
  },
  mixins: [modal],
  props: {
    // When no workspace is provided, the user must choose the workspace to install
    // the template into.
    workspace: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      // The content stays mounted while the modal is closed.
      open: false,
      loading: true,
      categories: [],
      selectedTemplate: null,
      selectedOwnerActions: false,
      tab: 'official',
      sharedSearch: '',
      // The list of the user's templates is loaded when its tab is opened first.
      userTemplatesOpened: false,
      // While a template is created, its modal takes the search shortcut.
      creating: false,
      // The user's template that is or was last updated. It's kept after the
      // update modal is closed, so that a running job stays monitored.
      updatedTemplate: null,
      updateMode: 'details',
      // While a template is updated, its modal takes the search shortcut.
      updating: false,
      // The user's template that is or was last asked to be deleted.
      deletedTemplate: null,
      // While a template is asked to be deleted, its modal takes the search
      // shortcut.
      deleting: false,
      // The user's template that is or was last asked to be made public.
      madePublicTemplate: null,
      // While a template is asked to be made public, its modal takes the search
      // shortcut.
      makingPublic: false,
      // The ids of the templates that are being made private.
      madePrivate: new Set(),
      // The id of the public template that was last opened, until it's loaded.
      selectingPublic: null,
    }
  },
  computed: {
    showTabs() {
      return (
        this.$featureFlagIsEnabled(FF_USER_TEMPLATES) &&
        this.$store.getters['auth/isAuthenticated']
      )
    },
    tabs() {
      return [
        {
          value: 'official',
          label: this.$t('templateModal.officialTemplates'),
          icon: 'baserow-icon-templates',
        },
        {
          value: 'public',
          label: this.$t('templateModal.publicTemplates'),
          icon: 'iconoir-group',
        },
        {
          value: 'own',
          label: this.$t('templateModal.yourTemplates'),
          icon: 'iconoir-box',
        },
      ]
    },
    tabIndex() {
      return this.tabs.findIndex((tab) => tab.value === this.tab)
    },
    selectedTemplateCategories() {
      // A user template lists its own categories.
      if (this.selectedTemplate.type === 'user') {
        return this.selectedTemplate.categories
      }
      return this.categories.filter((category) =>
        category.templates.some((t) => t.id === this.selectedTemplate.id)
      )
    },
  },
  watch: {
    open(open) {
      // The search of the page behind the modal closes all modals, so the modal keeps
      // the shortcut while it's open. The list and nested modals listen with a higher
      // priority.
      this.$priorityBus.$off('start-search', this.searchStarted)
      if (open) {
        this.$priorityBus.$on(
          'start-search',
          this.$priorityBus.level.MEDIUM,
          this.searchStarted
        )
      }
    },
  },
  beforeUnmount() {
    this.$priorityBus.$off('start-search', this.searchStarted)
  },
  methods: {
    isOwnTemplate,
    /**
     * Opens the modal on the details of the template with the provided id or
     * slug, or else of the default template.
     */
    async show(templateId = null, ...args) {
      if (!(await this.openAndLoad(...args))) {
        return
      }
      const template = this.categories
        .flatMap((category) => category.templates)
        .find((t) =>
          templateId === null
            ? t.is_default
            : t.id === templateId || t.slug === templateId
        )
      if (template) {
        this.selectTemplate(template)
      }
    },
    async showShared(search) {
      if (await this.openAndLoad()) {
        this.sharedSearch = search
        this.tab = 'public'
      }
    },
    /**
     * Opens the modal and fetches all the templates and their categories, so
     * that the user can browse them.
     *
     * @returns {Promise<boolean>} False if they couldn't be fetched, which closes
     *   the modal.
     */
    async openAndLoad(...args) {
      modal.methods.show.call(this, ...args)

      this.loading = true
      this.categories = []
      this.selectTemplate(null)
      this.tab = 'official'
      this.sharedSearch = ''
      this.userTemplatesOpened = false

      try {
        const { data } = await TemplateService(this.$client).fetchAll()
        this.categories = data
        this.loading = false
        return true
      } catch (error) {
        notifyIf(error, 'templates')
        this.hide()
        return false
      }
    },
    selectTab(tab) {
      this.tab = tab
      this.sharedSearch = ''
      if (tab === 'own') {
        this.userTemplatesOpened = true
      }
    },
    selectTemplate(template, own = false) {
      this.selectedTemplate = template
      this.selectedOwnerActions = own
    },
    /**
     * Shows the public template as it is now, which may have been made private or
     * deleted since the list was loaded. The list is loaded again then.
     */
    async selectPublicTemplate(template) {
      const { id, slug } = template
      this.selectingPublic = id
      try {
        const { data } = await TemplateService(this.$client).fetch(slug)
        if (this.selectingPublic === id && this.selectedTemplate === null) {
          this.selectTemplate(data, isOwnTemplate(data))
        }
      } catch (error) {
        if (error.response?.status === 404) {
          this.$store.dispatch('toast/error', {
            title: this.$t('templateModal.unavailableTitle'),
            message: this.$t('templateModal.unavailableDescription'),
          })
          this.$refs.publicTemplateList?.refresh()
        } else {
          notifyIf(error, 'templates')
        }
      } finally {
        if (this.selectingPublic === id) {
          this.selectingPublic = null
        }
      }
    },
    openCreateModal() {
      this.creating = true
      this.$refs.createUserTemplateModal.show()
    },
    templateCreated() {
      this.$refs.userTemplateList?.refresh()
    },
    moderated() {
      this.$refs.userTemplateList?.refresh()
      this.$refs.publicTemplateList?.refresh()
    },
    async openUpdateModal(template, mode) {
      // Only one update runs at a time. Its modal is shown again instead, also
      // while it's being sent, because mounting the modal of another template
      // stops monitoring the running job.
      const current = this.$refs.updateUserTemplateModal
      if (current?.jobIsRunning || current?.updateLoading) {
        this.updating = true
        current.show()
        return
      }
      this.updatedTemplate = template
      this.updateMode = mode
      this.updating = true
      // Mounts the modal of another template first.
      await this.$nextTick()
      this.$refs.updateUserTemplateModal.show()
    },
    /**
     * The list and the opened preview show the new revision. The updated template
     * is among the most recently updated ones of the user.
     */
    async templateUpdated(job) {
      this.$refs.userTemplateList?.refresh()
      this.$refs.publicTemplateList?.refresh()
      if (
        !this.selectedOwnerActions ||
        this.selectedTemplate?.id !== job.template
      ) {
        return
      }
      try {
        const { data } = await TemplateService(this.$client).fetchOwn()
        const template = data.results.find(({ id }) => id === job.template)
        if (template && this.selectedTemplate?.id === job.template) {
          this.selectedTemplate = template
        }
      } catch (error) {
        notifyIf(error, 'templates')
      }
    },
    /**
     * An install was refused because the template was updated since it was
     * shown, in another tab for example, or because another revision of a public
     * template was listed since. The preview then shows the new revision.
     */
    async templateOutdated() {
      if (this.selectedOwnerActions) {
        return this.templateUpdated({ template: this.selectedTemplate.id })
      }
      const { id, slug } = this.selectedTemplate
      try {
        const { data } = await TemplateService(this.$client).fetch(slug)
        if (!this.selectedOwnerActions && this.selectedTemplate?.id === id) {
          this.selectedTemplate = data
        }
      } catch (error) {
        notifyIf(error, 'templates')
      }
    },
    async openDeleteModal(template) {
      this.deletedTemplate = template
      this.deleting = true
      // Mounts the modal the first time.
      await this.$nextTick()
      this.$refs.deleteUserTemplateModal.show()
    },
    async makePrivate({ id, slug }) {
      if (this.madePrivate.has(id)) {
        return
      }
      this.madePrivate.add(id)
      try {
        const { data } = await TemplateService(this.$client).setVisibility(
          slug,
          'private'
        )
        this.templateChanged(data)
      } catch (error) {
        notifyIf(error, 'templates')
      } finally {
        this.madePrivate.delete(id)
      }
    },
    /**
     * Shows the changed visibility of a user's template in the lists, its preview
     * and its update modal.
     *
     * @param {object} template The template as listed in the user's templates.
     */
    templateChanged(template) {
      this.$refs.userTemplateList?.replace(template)
      this.$refs.publicTemplateList?.refresh()
      if (
        this.selectedOwnerActions &&
        this.selectedTemplate?.id === template.id
      ) {
        this.selectedTemplate = template
      }
      if (this.updatedTemplate?.id === template.id) {
        this.updatedTemplate = template
      }
    },
    async openMakePublicModal(template) {
      this.madePublicTemplate = template
      this.makingPublic = true
      // Mounts the modal the first time.
      await this.$nextTick()
      this.$refs.makeTemplatePublicModal.show()
    },
    /**
     * The deleted template disappears from the list, its preview and its update
     * modal, which stops following a job of the template. A template that was
     * already deleted may be left out of the list's count already, so the list is
     * loaded again instead.
     */
    templateDeleted(templateId, alreadyDeleted, requestedAt) {
      if (alreadyDeleted) {
        this.$refs.userTemplateList?.refresh()
      } else {
        this.$refs.userTemplateList?.remove(templateId, requestedAt)
      }
      this.$refs.publicTemplateList?.refresh()
      if (
        this.selectedOwnerActions &&
        this.selectedTemplate?.id === templateId
      ) {
        this.selectTemplate(null)
      }
      if (this.updatedTemplate?.id === templateId) {
        this.updatedTemplate = null
        this.updating = false
      }
    },
    /**
     * Called however the modal is closed, also with escape or a click outside. The
     * content stays mounted, so the template is cleared to unmount its preview,
     * whose search would otherwise keep answering the shortcut.
     */
    hidden() {
      this.open = false
      // A public template still being opened isn't shown once the modal is closed.
      this.selectingPublic = null
      this.selectTemplate(null)
    },
    searchStarted({ event }) {
      event.preventDefault()
    },
  },
}
</script>
