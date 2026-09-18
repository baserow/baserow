<template>
  <div
    class="application-card"
    role="link"
    tabindex="0"
    @click="select()"
    @keydown.enter="selectWithKeyboard($event)"
    @keydown.space="selectWithKeyboard($event)"
  >
    <div
      class="application-card__icon"
      :class="`application-card__icon--${application.type}`"
    >
      <div v-if="application._.loading" class="loading"></div>
      <i v-else :class="application._.type.iconClass"></i>
    </div>

    <div class="application-card__details">
      <div class="application-card__name">
        <SearchHighlight
          v-if="highlight !== ''"
          :text="application.name"
          :query="highlight"
        ></SearchHighlight>
        <Editable
          v-else
          ref="rename"
          :value="application.name"
          @change="renameApplication(application, $event)"
        ></Editable>
      </div>
      <div class="application-card__meta">
        {{ getApplicationTypeName(application) }}
        <span class="application-card__meta-separator">&#8226;</span>
        {{ dateMeta }}
      </div>
    </div>

    <ButtonIcon
      class="application-card__more"
      icon="baserow-icon-more-vertical"
      @click.stop="
        $refs.context.toggle($event.currentTarget, 'bottom', 'right', 0)
      "
    ></ButtonIcon>

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
import SearchHighlight from '@baserow/modules/core/components/SearchHighlight'
import { getHumanPeriodAgoCount } from '@baserow/modules/core/utils/date'
import {
  SORT_BY_CREATED,
  SORT_BY_LAST_VIEWED,
} from '@baserow/modules/core/utils/allWorkspaces'

export default {
  name: 'AllWorkspacesApplicationCard',
  components: { SearchHighlight },
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
    highlight: {
      type: String,
      required: false,
      default: '',
    },
    sortBy: {
      type: String,
      required: false,
      default: SORT_BY_LAST_VIEWED,
    },
  },
  emits: ['click'],
  computed: {
    dateMeta() {
      // The creation date only matters while sorting by it; every other sort
      // shows when the user last opened the application.
      if (this.sortBy === SORT_BY_CREATED) {
        return this.$t('common.createdAgo', {
          ago: this.humanAgo(this.application.created_on),
        })
      }
      if (!this.application.last_viewed) {
        return this.$t('common.neverViewed')
      }
      return this.$t('common.viewedAgo', {
        ago: this.humanAgo(this.application.last_viewed),
      })
    },
  },
  methods: {
    humanAgo(dateTime) {
      const { period, count } = getHumanPeriodAgoCount(dateTime)
      // Same wording as the `timeAgo` mixin for moments that are seconds old,
      // which a just opened application always is.
      if (period === 'seconds') {
        return this.$t(
          count <= 5 ? 'datetime.justNow' : 'datetime.lessThanMinuteAgo'
        )
      }
      return this.$t(`datetime.${period}Ago`, { count })
    },
    select() {
      // Clicking inside the name while it's being renamed inline must not
      // open the application.
      if (this.$refs.rename?.editing) {
        return
      }
      this.$emit('click')
    },
    selectWithKeyboard(event) {
      // Only when the card itself is focused, so typing in the inline rename or
      // pressing enter on the context button keeps its own behaviour.
      if (event.target !== event.currentTarget) {
        return
      }
      event.preventDefault()
      this.select()
    },
    handleRenameApplication() {
      // There is no inline editable in search results mode because the name is
      // rendered with the match highlighted.
      this.$refs.rename?.edit()
    },
  },
}
</script>
