<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <div class="context__menu-title">{{ view.name }} ({{ view.id }})</div>
    <ul class="context__menu">
      <component
        :is="component"
        v-for="(component, i) in additionalContextComponents"
        :key="i"
        :workspace="database.workspace"
        :database="database"
        :table="table"
        :view="view"
        @hide-context="$refs.context.hide()"
      />
      <li
        v-if="
          hasValidExporter &&
          $hasPermission(
            'database.table.run_export',
            table,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="exportView()">
          <i class="context__menu-item-icon iconoir-share-ios"></i>
          {{ $t('viewContext.exportView') }}
        </a>
      </li>
      <li
        v-if="
          $hasPermission(
            'database.table.import_rows',
            table,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="importFile()">
          <i class="context__menu-item-icon iconoir-import"></i>
          {{ $t('viewContext.importFile') }}
        </a>
      </li>
      <li
        v-if="
          $hasPermission(
            'database.table.view.duplicate',
            view,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          :class="{ 'context__menu-item-link--loading': duplicateLoading }"
          @click="duplicateView()"
        >
          <i class="context__menu-item-icon iconoir-copy"></i>
          {{ $t('viewContext.duplicateView') }}
        </a>
      </li>
      <li
        v-for="(
          changeViewOwnershipTypeComponent, index
        ) in changeViewOwnershipTypeMenuItems"
        :key="'view-ownership-type-' + index"
      >
        <component
          :is="changeViewOwnershipTypeComponent"
          :view="view"
          :database="database"
        ></component>
      </li>
      <li
        v-if="
          $hasPermission(
            'database.table.create_webhook',
            table,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="openWebhookModal()">
          <i class="context__menu-item-icon iconoir-globe"></i>
          {{ $t('viewContext.webhooks') }}
        </a>
      </li>
      <li
        v-if="
          $hasPermission(
            'database.table.view.update',
            view,
            database.workspace.id
          )
        "
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="enableRename()">
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('viewContext.renameView') }}
        </a>
      </li>
      <li
        v-if="
          $hasPermission(
            'database.table.view.delete',
            view,
            database.workspace.id
          )
        "
        class="context__menu-item context-menu-item--with-separator"
      >
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          :class="{ 'context__menu-item-link--loading': deleteLoading }"
          @click="deleteView()"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('viewContext.deleteView') }}
        </a>
      </li>
    </ul>
    <ExportTableModal
      ref="exportViewModal"
      :database="database"
      :table="table"
      :view="view"
    />
    <ImportFileModal
      ref="importFileModal"
      :database="database"
      :table="table"
      :fields="fields"
    />
    <WebhookModal ref="webhookModal" :database="database" :table="table" />
  </Context>
</template>

<script>
import { mapGetters } from 'vuex'
import context from '@baserow/modules/core/mixins/context'
import viewTypeHasExporterTypes from '@baserow/modules/database/utils/viewTypeHasExporterTypes'
import ImportFileModal from '@baserow/modules/database/components/table/ImportFileModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ExportTableModal from '@baserow/modules/database/components/export/ExportTableModal'
import WebhookModal from '@baserow/modules/database/components/webhook/WebhookModal.vue'

export default {
  name: 'ViewContext',
  components: {
    ExportTableModal,
    WebhookModal,
    ImportFileModal,
  },
  mixins: [context],
  props: {
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      duplicateLoading: false,
      deleteLoading: false,
    }
  },
  computed: {
    hasValidExporter() {
      return viewTypeHasExporterTypes(this.view.type, this.$registry)
    },
    ...mapGetters({
      fields: 'field/getAll',
    }),
    changeViewOwnershipTypeMenuItems() {
      const activeOwnershipTypes = Object.values(
        this.$registry.getAll('viewOwnershipType')
      )

      return activeOwnershipTypes
        .map((viewOwnershipType) => {
          return viewOwnershipType.getChangeOwnershipTypeMenuItemComponent()
        })
        .filter((component) => component !== null)
    },
    additionalContextComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .reduce(
          (components, plugin) =>
            components.concat(
              plugin.getAdditionalViewContextComponents(
                this.database.workspace,
                this.table,
                this.view
              )
            ),
          []
        )
        .filter((component) => component !== null)
    },
  },
  methods: {
    enableRename() {
      this.$refs.context.hide()
      this.$emit('enable-rename')
    },
    async deleteView() {
      this.deleteLoading = true

      try {
        await this.$store.dispatch('view/delete', this.view)
      } catch (error) {
        notifyIf(error, 'view')
      }

      this.deleteLoading = false
    },
    async duplicateView() {
      this.duplicateLoading = true
      let newView

      try {
        newView = await this.$store.dispatch('view/duplicate', this.view)
      } catch (error) {
        notifyIf(error, 'view')
      }

      this.$refs.context.hide()
      this.duplicateLoading = false

      // Redirect to the newly created view.
      this.$nuxt.$router.push({
        name: 'database-table',
        params: {
          databaseId: this.table.database_id,
          tableId: this.table.id,
          viewId: newView.id,
        },
      })
    },
    exportView() {
      this.$refs.context.hide()
      this.$refs.exportViewModal.show()
    },
    importFile() {
      this.$refs.context.hide()
      this.$refs.importFileModal.show()
    },
    openWebhookModal() {
      this.$refs.context.hide()
      this.$refs.webhookModal.show()
    },
  },
}
</script>
