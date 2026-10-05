import { Registerable } from '@baserow/modules/core/registry'

/**
 * Something that can be attached to a prompt or an instructions text through
 * the generic "+" picker (`PromptAttachments`): skills today, more later.
 * An attachment is a plain object `{ type, id, ...option }` so the host (an
 * agent, an AI field, a chat message) decides how it is persisted.
 */
export class PromptAttachmentType extends Registerable {
  /**
   * The group label in the picker.
   */
  getName() {
    throw new Error('getName must be implemented.')
  }

  getIconClass() {
    return 'iconoir-attachment'
  }

  getOrder() {
    return 50
  }

  /**
   * Loads whatever the items need (e.g. a store fetch). `context` holds the
   * workspace the prompt belongs to.
   */
  async fetchItems(context) {}

  /**
   * The attachable items `[{ id, label, description }]`.
   */
  getItems(context) {
    return []
  }

  getItem(context, id) {
    return this.getItems(context).find((item) => item.id === id)
  }

  /**
   * An optional setting per attachment, e.g. how a skill is used. The first
   * option is the default. `[{ value, label, description }]`.
   */
  getOptions(context) {
    return []
  }

  getOptionKey() {
    return 'mode'
  }

  /**
   * Where the items are managed: `{ label, settingsPage }` opens the
   * workspace settings modal on that page.
   */
  getManageAction(context) {
    return null
  }
}

export class SkillPromptAttachmentType extends PromptAttachmentType {
  static getType() {
    return 'skill'
  }

  getName() {
    return this.app.$i18n.t('promptAttachments.skills')
  }

  getIconClass() {
    return 'iconoir-book'
  }

  async fetchItems({ workspace }) {
    const store = this.app.$store
    if (!store.getters['workspaceSkill/isLoaded'](workspace.id)) {
      await store.dispatch('workspaceSkill/fetchAll', {
        workspaceId: workspace.id,
      })
    }
  }

  getItems({ workspace }) {
    return this.app.$store.getters['workspaceSkill/getAllInWorkspace'](
      workspace.id
    ).map((skill) => ({
      id: skill.id,
      label: skill.name,
      description: skill.description,
    }))
  }

  getOptions() {
    const { $i18n: i18n } = this.app
    return [
      {
        value: 'always',
        label: i18n.t('promptAttachments.skillAlways'),
        description: i18n.t('promptAttachments.skillAlwaysDescription'),
      },
      {
        value: 'on_demand',
        label: i18n.t('promptAttachments.skillOnDemand'),
        description: i18n.t('promptAttachments.skillOnDemandDescription'),
      },
    ]
  }

  getManageAction({ workspace }) {
    if (
      !this.app.$hasPermission('workspace.list_skills', workspace, workspace.id)
    ) {
      return null
    }
    return {
      label: this.app.$i18n.t('promptAttachments.manageSkills'),
      settingsPage: 'skills',
    }
  }
}
