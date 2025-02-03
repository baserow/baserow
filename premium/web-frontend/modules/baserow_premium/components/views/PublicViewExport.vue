<template>
  <li
    v-if="view.allow_public_export"
    class="header__filter-item header__filter-item--no-margin-left"
  >
    <a
      ref="target"
      class="header__filter-link"
      @click="$refs.context.toggle($event.target, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon baserow-icon-more-vertical"></i>
    </a>
    <Context ref="context">
      <ul class="context__menu">
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click=";[$refs.exportModal.show(), $refs.context.hide()]"
          >
            <i class="context__menu-item-icon iconoir-share-ios"></i>
            {{ $t('publicViewExport.export') }}
          </a>
        </li>
      </ul>
    </Context>
    <ExportTableModal
      ref="exportModal"
      :view="view"
      :table="table"
      :database="database"
      :start-export="startExport"
      :get-job="getJob"
      :enable-views-dropdown="false"
      :ad-hoc-filtering="true"
      :ad-hoc-sorting="true"
      :ad-hoc-fields="visibleOrderedFields"
    ></ExportTableModal>
  </li>
</template>

<script>
import ExportTableModal from '@baserow/modules/database/components/export/ExportTableModal'
import PublicViewExportService from '@baserow_premium/services/publicViewExport'

export default {
  name: 'PublicViewExport',
  components: { ExportTableModal },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    isPublicView: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  computed: {
    visibleOrderedFields() {
      const viewType = this.$registry.get('view', this.view.type)
      return viewType.getVisibleFieldsInOrder(
        this,
        this.fields,
        this.view,
        this.storePrefix
      )
    },
  },
  methods: {
    startExport({ view, values, client, filters, orderBy, fields }) {
      // There is no need to include the `view_id` in the body because we're already
      // providing the slug as path parameter.
      delete values.view_id
      values.filters = filters
      values.order_by = orderBy
      values.fields = fields === null ? null : fields.map((f) => f.id)
      const publicAuthToken =
        this.$store.getters['page/view/public/getAuthToken']
      return PublicViewExportService(client).export({
        slug: view.slug,
        values,
        publicAuthToken,
      })
    },
    getJob(job, client) {
      return PublicViewExportService(client).get(job.id)
    },
  },
}
</script>
