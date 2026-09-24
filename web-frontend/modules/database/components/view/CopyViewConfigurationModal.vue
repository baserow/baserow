<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('copyViewConfigurationModal.title', { name: view.name }) }}
    </h2>
    <Error :error="error"></Error>
    <div class="control margin-bottom-2">
      <label class="control__label control__label--small">
        {{ $t('copyViewConfigurationModal.sourceView') }}
      </label>
      <Dropdown
        v-model="sourceViewId"
        :show-search="true"
        :disabled="loading"
        @input="sourceViewChanged($event)"
      >
        <DropdownItem
          v-for="sourceViewItem in sourceViews"
          :key="sourceViewItem.id"
          :name="sourceViewItem.name"
          :value="sourceViewItem.id"
          :icon="sourceViewItem._.type.iconClass"
        ></DropdownItem>
      </Dropdown>
    </div>
    <div class="flex margin-bottom-2">
      <ButtonText
        size="small"
        :disabled="sourceView === undefined || loading"
        @click="selectAll()"
      >
        {{ $t('copyViewConfigurationModal.selectAll') }}
      </ButtonText>
      <ButtonText
        size="small"
        :disabled="sourceView === undefined || loading"
        @click="clearAll()"
      >
        {{ $t('copyViewConfigurationModal.clearAll') }}
      </ButtonText>
    </div>
    <SwitchInput
      v-for="option in destOptions"
      :key="option.getType()"
      small
      class="margin-bottom-1"
      :value="selected.includes(option.getType())"
      :disabled="!enabledKeys.includes(option.getType()) || loading"
      @input="toggle(option.getType(), $event)"
      >{{ option.getName(view) }}</SwitchInput
    >
    <div class="actions margin-bottom-0">
      <div class="align-right">
        <Button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="loading || !canSubmit"
          @click="submit()"
        >
          {{ $t('copyViewConfigurationModal.copy') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import { mapGetters } from 'vuex'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import {
  getCompatibleSourceViews,
  getDestinationCopyOptions,
  getEnabledCopyOptionKeys,
  copyViewConfiguration,
} from '@baserow/modules/database/utils/copyViewConfiguration'

export default {
  name: 'CopyViewConfigurationModal',
  mixins: [modal, error],
  props: {
    view: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      sourceViewId: null,
      selected: [],
      selectionChangedByUser: false,
      initialSelection: null,
    }
  },
  computed: {
    ...mapGetters({
      allViews: 'view/getAll',
    }),
    destOptions() {
      return getDestinationCopyOptions(this.$registry, this.view)
    },
    sourceViews() {
      // Views from which nothing can be copied, form views for example, are
      // excluded because selecting them would be a dead end.
      return getCompatibleSourceViews(
        this.$registry,
        this.allViews,
        this.view,
        this.database.workspace.id
      )
    },
    sourceView() {
      return this.sourceViews.find((view) => view.id === this.sourceViewId)
    },
    enabledKeys() {
      if (this.sourceView === undefined) {
        return []
      }
      return getEnabledCopyOptionKeys(
        this.$registry,
        this.sourceView,
        this.view,
        this.database.workspace.id
      )
    },
    canSubmit() {
      return (
        this.sourceView !== undefined &&
        this.selected.some((key) => this.enabledKeys.includes(key))
      )
    },
  },
  methods: {
    /**
     * The optional `initialSelection` array controls which options are checked
     * once a source view is chosen. When it's `null`, all enabled options are
     * checked.
     */
    show(initialSelection = null, ...args) {
      this.loading = false
      this.sourceViewId = null
      this.selected = []
      this.selectionChangedByUser = false
      this.initialSelection = initialSelection
      this.hideError()
      return modal.methods.show.call(this, ...args)
    },
    sourceViewChanged(viewId) {
      const sourceView = this.sourceViews.find((view) => view.id === viewId)
      if (sourceView === undefined) {
        return
      }
      const enabledKeys = getEnabledCopyOptionKeys(
        this.$registry,
        sourceView,
        this.view,
        this.database.workspace.id
      )
      if (!this.selectionChangedByUser) {
        this.selected = enabledKeys.filter(
          (key) =>
            this.initialSelection === null ||
            this.initialSelection.includes(key)
        )
      } else {
        // Keep the user's explicit selection when switching the source view,
        // but drop the options that the new source view doesn't support.
        this.selected = this.selected.filter((key) => enabledKeys.includes(key))
      }
    },
    toggle(key, value) {
      this.selectionChangedByUser = true
      if (value && !this.selected.includes(key)) {
        this.selected = [...this.selected, key]
      } else if (!value) {
        this.selected = this.selected.filter((k) => k !== key)
      }
    },
    selectAll() {
      this.selectionChangedByUser = true
      this.selected = [...this.enabledKeys]
    },
    clearAll() {
      this.selectionChangedByUser = true
      this.selected = []
    },
    async submit() {
      this.loading = true
      this.hideError()
      try {
        await copyViewConfiguration(this, {
          sourceView: this.sourceView,
          destView: this.view,
          categories: this.selected.filter((key) =>
            this.enabledKeys.includes(key)
          ),
          workspaceId: this.database.workspace.id,
        })
        this.hide()
      } catch (err) {
        this.handleError(err, 'view')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
