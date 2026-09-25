<template>
  <ItemCard
    :name="application.name"
    :icon="application._.type.iconClass"
    :icon-color="application._.type.iconColor"
    :loading="application._.loading"
    @click="select()"
  >
    <template #name>
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
    </template>

    <template #meta>
      {{ getApplicationTypeName(application) }}
      <span class="item-card__meta-separator">&#8226;</span>
      {{ dateMeta }}
    </template>

    <template #actions>
      <ButtonIcon
        class="item-card__more"
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
    </template>
  </ItemCard>
</template>

<script>
import application from '@baserow/modules/core/mixins/application'
import ItemCard from '@baserow/modules/core/components/ItemCard'
import SearchHighlight from '@baserow/modules/core/components/SearchHighlight'
import { getHumanAgoLabel } from '@baserow/modules/core/utils/date'
import { injectNow } from '@baserow/modules/core/composables/useNow'
import {
  SORT_BY_CREATED,
  SORT_BY_LAST_VIEWED,
} from '@baserow/modules/core/utils/allWorkspaces'

export default {
  name: 'AllWorkspacesApplicationCard',
  components: { ItemCard, SearchHighlight },
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
  setup() {
    return { now: injectNow() }
  },
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
    dateMeta() {
      // Reading the shared clock makes this re-evaluate as time passes.
      const now = this.now ?? undefined
      // The creation date only matters while sorting by it; every other sort
      // shows when the user last opened the application.
      if (this.sortBy === SORT_BY_CREATED) {
        return this.$t('common.createdAgo', {
          ago: getHumanAgoLabel(this.$t, this.application.created_on, now),
        })
      }
      if (!this.application.last_viewed) {
        return this.$t('common.neverViewed')
      }
      return this.$t('common.viewedAgo', {
        ago: getHumanAgoLabel(this.$t, this.application.last_viewed, now),
      })
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
