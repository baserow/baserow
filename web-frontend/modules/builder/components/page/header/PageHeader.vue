<template>
  <header class="layout__col-2-1 header header--space-between">
    <SkeletonBlock
      v-if="loading"
      class="header__loading"
      width="140px"
      height="12px"
    ></SkeletonBlock>
    <template v-else>
      <PageHeaderMenuItems />
      <ApplicationUntrustedContentAlert
        :key="builder.id"
        :content-owner="builder"
        :can-trust="
          $hasPermission('application.update', builder, builder.workspace.id)
        "
        :trust-content="trustContent"
        :message="$t('builderUntrustedContent.warning')"
      />
      <DeviceSelector
        :device-type-selected="deviceTypeSelected"
        @selected="actionSetDeviceTypeSelected"
      />
      <PageActions />
    </template>
  </header>
</template>

<script>
import ApplicationUntrustedContentAlert from '@baserow/modules/core/components/application/ApplicationUntrustedContentAlert'
import DeviceSelector from '@baserow/modules/builder/components/page/header/DeviceSelector'
import PageHeaderMenuItems from '@baserow/modules/builder/components/page/header/PageHeaderMenuItems'
import PageActions from '@baserow/modules/builder/components/page/header/PageActions'
import { mapActions, mapGetters } from 'vuex'

export default {
  name: 'PageHeader',
  components: {
    ApplicationUntrustedContentAlert,
    PageHeaderMenuItems,
    DeviceSelector,
    PageActions,
  },
  inject: ['builder'],
  props: {
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    ...mapGetters({ deviceTypeSelected: 'page/getDeviceTypeSelected' }),
    deviceTypes() {
      return Object.values(this.$registry.getOrderedList('device'))
    },
  },
  created() {
    if (this.deviceTypeSelected === null) {
      this.$store.dispatch(
        'page/setDeviceTypeSelected',
        this.deviceTypes[0].getType()
      )
    }
  },
  methods: {
    trustContent() {
      return this.$store.dispatch('application/update', {
        application: this.builder,
        values: { untrusted_content: false },
      })
    },
    ...mapActions({
      actionSetDeviceTypeSelected: 'page/setDeviceTypeSelected',
    }),
  },
}
</script>
