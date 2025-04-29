<template>
  <Context overflow-scroll max-height-if-outside-viewport>
    <ul class="select__items prevent-scroll">
      <li
        v-for="(mode, index) in modes"
        :key="mode.getType()"
        v-tooltip="getTooltip(mode)"
        class="select__item select__item--no-options"
        :class="{ active: mode.type === view.mode }"
      >
        <a class="select__item-link" @click="select(mode, index)"
          ><span class="select__item-name">
            <i :class="`select__item-icon ${mode.getIconClass()}`"></i>
            <span class="select__item-name-text">{{ mode.getName() }}</span>
            <div v-if="isDeactivated(mode)" class="deactivated-label">
              <i class="iconoir-lock"></i>
            </div>
          </span>
          <div class="select__item-description">
            {{ mode.getDescription() }}
          </div>
        </a>
        <i
          v-if="mode.type === view.mode"
          class="select__item-active-icon iconoir-check"
        ></i>
        <component
          :is="mode.getDeactivatedClickModal()[0]"
          v-if="hasDeactivatedClickModal(mode)"
          :ref="'deactivatedClickModal' + index.toString()"
          v-bind="mode.getDeactivatedClickModal()[1]"
          :name="mode.getName()"
          :workspace="database.workspace"
        ></component>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'FormViewModeContext',
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
  },
  computed: {
    modes() {
      return Object.values(this.$registry.getAll('formViewMode'))
    },
  },
  methods: {
    isDeactivated(mode) {
      return mode.isDeactivated(this.database.workspace.id)
    },
    hasDeactivatedClickModal(mode) {
      return mode.getDeactivatedClickModal() !== null
    },
    getTooltip(mode) {
      if (this.isDeactivated(mode)) {
        return mode.getDeactivatedText()
      }
      return ''
    },
    async select(mode, index) {
      if (this.isDeactivated(mode)) {
        if (this.hasDeactivatedClickModal(mode)) {
          this.$refs['deactivatedClickModal' + index.toString()][0].show()
        }
        return
      }

      this.hide()

      if (this.view.mode !== mode.type) {
        try {
          await this.$store.dispatch('view/update', {
            view: this.view,
            values: {
              mode: mode.type,
            },
          })
        } catch (error) {
          notifyIf(error, 'view')
        }
      }
    },
  },
}
</script>
