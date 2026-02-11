<template>
  <div class="dashboard__application">
    <div class="dashboard__application-wrapper" @click="$emit('click')">
      <div class="dashboard__application-icon">
        <i :class="application._.type.iconClass"></i>
      </div>

      <div class="dashboard__application-details">
        <div class="dashboard__application-name">
          <div class="dashboard__application-name-text">
            <Editable
              ref="rename"
              :value="application.name"
              @change="renameApplication(application, $event)"
            ></Editable>
          </div>
        </div>

        <div class="dashboard__application-more">
          {{ getApplicationTypeName(application) }}
          <span class="dashboard__application-more-separator">&#8226;</span>
          {{ $t('dashboardApplication.createdAt') }} {{ humanCreatedAt }}
        </div>
      </div>
    </div>

    <span ref="contextLink" class="dashboard__application-more-button">
      <ButtonIcon
        icon="baserow-icon-more-vertical"
        @click="$refs.context.toggle($refs.contextLink, 'bottom', 'right', 0)"
      ></ButtonIcon>
    </span>

    <component
      :is="getApplicationContextComponent(application)"
      ref="context"
      :application="application"
      :workspace="workspace"
      @rename="handleRenameApplication()"
    ></component>
  </div>
</template>

<script>
import application from '@baserow/modules/core/mixins/application'
import { getHumanPeriodAgoCount } from '@baserow/modules/core/utils/date'

export default {
  mixins: [application],
  props: {
    application: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['click'],
  computed: {
    humanCreatedAt() {
      const { period, count } = getHumanPeriodAgoCount(
        this.application.created_on
      )
      return this.$t(`datetime.${period}Ago`, { count })
    },
  },
}
</script>
