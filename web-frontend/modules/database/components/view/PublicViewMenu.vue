<template>
  <li
    v-if="reportingEnabled || additionalMenuItems.length > 0"
    class="header__filter-item header__filter-item--no-margin-left"
  >
    <a
      ref="target"
      class="header__filter-link"
      href="#"
      :title="$t('publicViewMenu.moreOptions')"
      @click.prevent="$refs.context.toggle($event.target, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon baserow-icon-more-vertical"></i>
    </a>
    <Context ref="context">
      <ul class="context__menu" @click="$refs.context.hide()">
        <component
          :is="component"
          v-for="(component, index) in additionalMenuItems"
          :key="index"
          :database="database"
          :table="table"
          :view="view"
          :fields="fields"
          :store-prefix="storePrefix"
        ></component>
        <li v-if="reportingEnabled" class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click="$refs.reportAbuseModal.show()"
          >
            <i class="context__menu-item-icon iconoir-warning-triangle"></i>
            {{ $t('publicViewMenu.reportAbuse') }}
          </a>
        </li>
      </ul>
    </Context>
    <ReportAbuseModal
      ref="reportAbuseModal"
      resource-type="database_view"
      :identifier="view.slug"
      :request-config="requestConfig"
    ></ReportAbuseModal>
  </li>
</template>

<script>
import ReportAbuseModal from '@baserow/modules/core/components/abuseReport/ReportAbuseModal'
import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'

export default {
  name: 'PublicViewMenu',
  components: { ReportAbuseModal },
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
    storePrefix: {
      type: String,
      required: true,
    },
  },
  computed: {
    reportingEnabled() {
      return this.$store.getters['settings/get'].allow_reporting_abuse !== false
    },
    additionalMenuItems() {
      return Object.values(this.$registry.getAll('plugin'))
        .reduce(
          (components, plugin) =>
            components.concat(
              plugin.getAdditionalPublicViewMenuItems(this.view)
            ),
          []
        )
        .filter((component) => component !== null)
    },
    requestConfig() {
      const publicAuthToken =
        this.$store.getters['page/view/public/getAuthToken']
      return publicAuthToken
        ? addPublicAuthTokenHeader({}, publicAuthToken)
        : {}
    },
  },
}
</script>
