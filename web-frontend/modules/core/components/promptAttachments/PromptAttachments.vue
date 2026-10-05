<template>
  <div class="prompt-attachments">
    <template
      v-for="attachment in attachments"
      :key="attachmentKey(attachment)"
    >
      <Chips
        :ref="`chip-${attachmentKey(attachment)}`"
        :icon="typeOf(attachment)?.getIconClass()"
        :disabled="disabled"
        class="prompt-attachments__chip"
        @click="openAttachment(attachment)"
      >
        <span class="prompt-attachments__chip-label">
          {{ labelOf(attachment) }}
        </span>
        <span
          v-if="optionLabel(attachment)"
          class="prompt-attachments__chip-option"
        >
          {{ optionLabel(attachment) }}
        </span>
      </Chips>
      <Context
        :ref="`context-${attachmentKey(attachment)}`"
        overflow-scroll
        max-height-if-outside-viewport
      >
        <ul class="context__menu">
          <li
            v-for="option in optionsOf(attachment)"
            :key="option.value"
            class="context__menu-item"
          >
            <a
              class="context__menu-item-link"
              @click="setOption(attachment, option.value)"
            >
              <i
                class="context__menu-item-icon"
                :class="
                  attachment[optionKeyOf(attachment)] === option.value
                    ? 'iconoir-check-circle'
                    : 'iconoir-circle'
                "
              ></i>
              <span class="prompt-attachments__option">
                <span>{{ option.label }}</span>
                <span class="prompt-attachments__option-description">
                  {{ option.description }}
                </span>
              </span>
            </a>
          </li>
          <li
            class="context__menu-item"
            :class="{
              'context__menu-item--with-separator':
                optionsOf(attachment).length > 0,
            }"
          >
            <a
              class="context__menu-item-link context__menu-item-link--delete"
              @click="remove(attachment)"
            >
              <i class="context__menu-item-icon iconoir-bin"></i>
              {{ $t('promptAttachments.remove') }}
            </a>
          </li>
        </ul>
      </Context>
    </template>
    <ButtonIcon
      v-if="!disabled"
      ref="addButton"
      type="secondary"
      icon="iconoir-plus"
      class="prompt-attachments__add"
      :title="$t('promptAttachments.add')"
      :loading="loading"
      @click="openPicker"
    />
    <Context
      ref="picker"
      class="prompt-attachments__picker"
      max-height-if-outside-viewport
      @shown="$refs.menu?.focus()"
    >
      <GroupedMenu
        ref="menu"
        :items="menuItems"
        :search-placeholder="$t('promptAttachments.search')"
        :empty-text="$t('promptAttachments.nothingToAdd')"
        @select="add($event)"
        @close="$refs.picker.hide()"
      />
      <div v-if="manageActions.length > 0" class="prompt-attachments__manage">
        <a
          v-for="action in manageActions"
          :key="action.type"
          class="prompt-attachments__manage-link"
          @click.prevent="manage(action)"
        >
          <i class="iconoir-settings"></i>
          {{ action.label }}
        </a>
      </div>
    </Context>
    <WorkspaceSettingsModal
      ref="workspaceSettingsModal"
      :workspace="workspace"
    />
  </div>
</template>

<script>
import WorkspaceSettingsModal from '@baserow/modules/core/components/workspace/WorkspaceSettingsModal'
import GroupedMenu from '@baserow/modules/core/components/GroupedMenu'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * The generic "+" picker shown under a prompt or instructions input. It lists
 * everything that can be attached (the registered `promptAttachment` types,
 * skills first) and shows the attachments as chips. Clicking a chip changes
 * its option (for skills: always or on demand) or removes it.
 *
 * Attachments are plain `{ type, id, ...option }` objects; the host persists
 * them however it wants and feeds them back through the `attachments` prop.
 */
export default {
  name: 'PromptAttachments',
  components: { GroupedMenu, WorkspaceSettingsModal },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    attachments: {
      type: Array,
      required: true,
    },
    // Limit the picker to these attachment types; every type when empty.
    types: {
      type: Array,
      required: false,
      default: () => [],
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['add', 'update', 'remove'],
  data() {
    return { loading: false, fetched: false }
  },
  computed: {
    context() {
      return { workspace: this.workspace }
    },
    attachmentTypes() {
      return this.$registry
        .getOrderedList('promptAttachment')
        .filter(
          (type) =>
            this.types.length === 0 || this.types.includes(type.getType())
        )
    },
    menuItems() {
      const attached = new Set(this.attachments.map(this.attachmentKey))
      return this.attachmentTypes
        .map((type) => ({
          id: type.getType(),
          label: type.getName(),
          icon: type.getIconClass(),
          iconColor: 'muted-blue',
          children: type
            .getItems(this.context)
            .filter((item) => !attached.has(`${type.getType()}-${item.id}`))
            .map((item) => ({
              id: `${type.getType()}-${item.id}`,
              label: item.label,
              value: item.id,
              icon: type.getIconClass(),
              iconColor: 'muted-blue',
              description: item.description,
              meta: { type, item },
            })),
        }))
        .filter((group) => group.children.length > 0)
    },
    manageActions() {
      return this.attachmentTypes
        .map((type) => ({
          type: type.getType(),
          ...(type.getManageAction(this.context) || {}),
        }))
        .filter((action) => action.label)
    },
  },
  async mounted() {
    // The chips need the item labels right away.
    await this.ensureFetched()
  },
  methods: {
    attachmentKey(attachment) {
      return `${attachment.type}-${attachment.id}`
    },
    typeOf(attachment) {
      try {
        return this.$registry.get('promptAttachment', attachment.type)
      } catch {
        return null
      }
    },
    labelOf(attachment) {
      return (
        this.typeOf(attachment)?.getItem(this.context, attachment.id)?.label ||
        this.$t('promptAttachments.unknown')
      )
    },
    optionsOf(attachment) {
      return this.typeOf(attachment)?.getOptions(this.context) || []
    },
    optionKeyOf(attachment) {
      return this.typeOf(attachment)?.getOptionKey() || 'mode'
    },
    optionLabel(attachment) {
      const key = this.optionKeyOf(attachment)
      return this.optionsOf(attachment).find(
        (option) => option.value === attachment[key]
      )?.label
    },
    async ensureFetched() {
      if (this.fetched) {
        return
      }
      this.loading = true
      try {
        await Promise.all(
          this.attachmentTypes.map((type) => type.fetchItems(this.context))
        )
        this.fetched = true
      } catch (error) {
        notifyIf(error, 'workspace')
      } finally {
        this.loading = false
      }
    },
    async openPicker(event) {
      await this.ensureFetched()
      this.$refs.picker.toggle(
        event.currentTarget || this.$refs.addButton.$el,
        'bottom',
        'left',
        4
      )
    },
    openAttachment(attachment) {
      if (this.disabled) {
        return
      }
      const key = this.attachmentKey(attachment)
      const chip = this.$refs[`chip-${key}`]?.[0]
      const context = this.$refs[`context-${key}`]?.[0]
      context?.toggle(chip?.$el || chip, 'bottom', 'left', 4)
    },
    add({ meta }) {
      this.$refs.picker.hide()
      const { type, item } = meta
      const option = type.getOptions(this.context)[0]
      const attachment = { type: type.getType(), id: item.id }
      if (option) {
        attachment[type.getOptionKey()] = option.value
      }
      this.$emit('add', attachment)
    },
    setOption(attachment, value) {
      this.$refs[`context-${this.attachmentKey(attachment)}`]?.[0]?.hide()
      const key = this.optionKeyOf(attachment)
      if (attachment[key] !== value) {
        this.$emit('update', { ...attachment, [key]: value })
      }
    },
    remove(attachment) {
      this.$refs[`context-${this.attachmentKey(attachment)}`]?.[0]?.hide()
      this.$emit('remove', attachment)
    },
    manage(action) {
      this.$refs.picker.hide()
      this.$refs.workspaceSettingsModal.show(action.settingsPage)
    },
  },
}
</script>
