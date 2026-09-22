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
          v-if="!showEditable"
          :text="application.name"
          :query="highlight"
        ></SearchHighlight>
        <Editable
          v-show="showEditable"
          ref="rename"
          :value="application.name"
          @editing="editing = $event"
          @change="rename($event)"
        ></Editable>
      </div>
      <div class="application-card__meta">
        {{ getApplicationTypeName(application) }}
        <span class="application-card__meta-separator">&#8226;</span>
        {{ $t('allWorkspaces.created') }} {{ humanCreatedAt }}
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
  },
  emits: ['click'],
  data() {
    return {
      editing: false,
      saving: false,
    }
  },
  computed: {
    showEditable() {
      return this.highlight === '' || this.editing || this.saving
    },
    humanCreatedAt() {
      const { period, count } = getHumanPeriodAgoCount(
        this.application.created_on
      )
      return this.$t(`datetime.${period}Ago`, { count })
    },
  },
  methods: {
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
      this.$refs.rename.edit()
    },
    async rename(event) {
      this.saving = true
      await this.renameApplication(this.application, event)
      this.saving = false
    },
  },
}
</script>
