<template>
  <div class="dashboard-app__content-header">
    <div class="dashboard-app__title">
      <Editable
        ref="dashboardNameEditable"
        :value="dashboard.name"
        @change="renameApplication(dashboard, $event)"
        @editing="editingDashboardName = $event"
      ></Editable>
      <a
        v-if="isEditMode"
        class="dashboard-app__edit"
        :class="{ 'visibility-hidden': editingDashboardName }"
        @click="editName"
      >
        <i class="dashboard-app__edit-icon iconoir-edit-pencil"></i
      ></a>
    </div>
    <div
      v-if="isEditMode || dashboard.description"
      class="dashboard-app__description"
    >
      <Editable
        ref="dashboardDescriptionEditable"
        :value="dashboard.description"
        :placeholder="$t('dashboard.descriptionPlaceholder')"
        @change="updateDescription(dashboard, $event)"
        @editing="editingDashboardDescription = $event"
      ></Editable>
      <a
        v-if="isEditMode"
        class="dashboard-app__edit"
        :class="{ 'visibility-hidden': editingDashboardDescription }"
        @click="editDescription"
      >
        <i class="dashboard-app__edit-icon iconoir-edit-pencil"></i
      ></a>
    </div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapGetters, mapActions } from 'vuex'

export default {
  name: 'DashboardContentHeader',
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      editingDashboardName: false,
      editingDashboardDescription: false,
    }
  },
  computed: {
    ...mapGetters({
      isEditMode: 'dashboardApplication/isEditMode',
      isEmpty: 'dashboardApplication/isEmpty',
    }),
  },
  methods: {
    ...mapActions({
      selectWidget: 'dashboardApplication/selectWidget',
    }),
    editName() {
      this.$refs.dashboardNameEditable.edit()
      this.editingDashboardName = true
      this.selectWidget(null)
    },
    editDescription() {
      this.$refs.dashboardDescriptionEditable.edit()
      this.editingDashboardDescription = true
      this.selectWidget(null)
    },
    async renameApplication(application, event) {
      try {
        await this.$store.dispatch('application/update', {
          application,
          values: {
            name: event.value,
          },
        })
      } catch (error) {
        this.$refs.dashboardNameEditable.set(event.oldValue)
        notifyIf(error, 'application')
      } finally {
        this.editingDashboardName = false
      }
    },
    async updateDescription(application, event) {
      try {
        await this.$store.dispatch('application/update', {
          application,
          values: {
            description: event.value,
          },
        })
      } catch (error) {
        this.$refs.dashboardDescriptionEditable.set(event.oldValue)
        notifyIf(error, 'application')
      } finally {
        this.editingDashboardDescription = false
      }
    },
  },
}
</script>
