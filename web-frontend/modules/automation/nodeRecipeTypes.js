import { Registerable } from '@baserow/modules/core/registry'
import {
  CoreGotoNodeType,
  CoreIteratorNodeType,
  LocalBaserowListRowsActionNodeType,
} from '@baserow/modules/automation/nodeTypes'
import { parseAliases } from '@baserow/modules/automation/utils/aliases'

/**
 * Service formula values are objects, not strings: the backend wraps a bare
 * string as a simple-mode formula, and the editor then shows a function call
 * as plain text. Recipes write function calls, so they must be advanced.
 */
const advancedFormula = (formula) => ({ formula, mode: 'advanced' })

/**
 * The add-node menu group every recipe is listed under. Its `order` puts it
 * after the node type groups, which have none and sort alphabetically.
 */
export const getRecipesGroup = (app) => ({
  id: 'recipes',
  label: app.$i18n.t('nodeRecipe.groupLabel'),
  icon: 'iconoir-repeat',
  iconColor: 'muted-purple',
  order: 1,
})

/**
 * A recipe is an add-node menu entry that inserts one or more real,
 * pre-configured nodes. It is not a node type: the backend never sees a
 * recipe, and `create` composes the store's existing node actions through the
 * `addNode` helper it is handed, so the inserted nodes are ordinary nodes the
 * user can edit, move or delete like any other.
 */
export class NodeRecipeType extends Registerable {
  /**
   * The name shown in the add-node menu.
   * @returns {string}
   */
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The description shown under the name in the add-node menu. It is also
   * matched by the menu search.
   * @returns {string}
   */
  get description() {
    throw new Error('Must be set on the type.')
  }

  /**
   * Extra terms the add-node menu search matches, besides the name and the
   * description.
   * @returns {string[]}
   */
  get aliases() {
    return []
  }

  get iconClass() {
    throw new Error('Must be set on the type.')
  }

  get group() {
    return getRecipesGroup(this.app)
  }

  get iconColor() {
    return this.group.iconColor
  }

  /**
   * Whether the recipe is offered in the add-node menu at all.
   * @returns {boolean}
   */
  isEnabled() {
    return true
  }

  /**
   * Inserts the recipe's nodes. `addNode` creates one node and applies its
   * optional `label` and `service` values; it resolves to the node as stored,
   * with its server `id` and `service.id`, so later nodes can reference it.
   * The first node must be inserted at the given `referenceNode`, `position`
   * and `output`, which is where the user clicked.
   * @param {object} workflow - The workflow to insert into.
   * @param {object} referenceNode - The node the insertion is relative to.
   * @param {string} position - 'north', 'south' or 'child' of the reference.
   * @param {string} output - The reference node's edge to insert on.
   * @param {function} addNode - ({ type, referenceNode, position, output,
   *   label, service }) => Promise<node>
   */
  async create({ workflow, referenceNode, position, output, addNode }) {
    throw new Error('This method must be implemented')
  }
}

/**
 * One Iterator over `range(5)`: runs its child nodes five times. The user
 * changes the range to loop more or fewer times.
 */
export class ForLoopNodeRecipeType extends NodeRecipeType {
  static getType() {
    return 'for_loop'
  }

  getOrder() {
    return 1
  }

  get name() {
    return this.app.$i18n.t('nodeRecipe.forLoopName')
  }

  get description() {
    return this.app.$i18n.t('nodeRecipe.forLoopDescription')
  }

  get aliases() {
    return parseAliases(this.app.$i18n.t('nodeRecipe.forLoopAliases'))
  }

  get iconClass() {
    return 'iconoir-repeat'
  }

  async create({ workflow, referenceNode, position, output, addNode }) {
    await addNode({
      type: CoreIteratorNodeType.getType(),
      referenceNode,
      position,
      output,
      label: this.app.$i18n.t('nodeRecipe.forLoopIteratorLabel'),
      service: { source: advancedFormula('range(5)') },
    })
  }
}

/**
 * A List rows node followed by a Go to node that jumps back to it while the
 * list is not empty. The List rows node is left unconfigured, exactly as if it
 * had been added by hand. The nodes the user puts between the two must change
 * those rows, or the loop only stops at the per-run dispatch limit.
 */
export class WhileLoopNodeRecipeType extends NodeRecipeType {
  static getType() {
    return 'while_loop'
  }

  getOrder() {
    return 2
  }

  get name() {
    return this.app.$i18n.t('nodeRecipe.whileLoopName')
  }

  get description() {
    return this.app.$i18n.t('nodeRecipe.whileLoopDescription')
  }

  get aliases() {
    return parseAliases(this.app.$i18n.t('nodeRecipe.whileLoopAliases'))
  }

  get iconClass() {
    return 'iconoir-refresh-double'
  }

  async create({ workflow, referenceNode, position, output, addNode }) {
    const listRows = await addNode({
      type: LocalBaserowListRowsActionNodeType.getType(),
      referenceNode,
      position,
      output,
      label: this.app.$i18n.t('nodeRecipe.whileLoopListRowsLabel'),
    })
    // 'south' of the list rows node is right whatever the first insertion
    // was (north, south or child): the backend derives the edge from the
    // reference node itself.
    await addNode({
      type: CoreGotoNodeType.getType(),
      referenceNode: listRows,
      position: 'south',
      output: '',
      label: this.app.$i18n.t('nodeRecipe.whileLoopGotoLabel'),
      service: {
        destination_service_id: listRows.service.id,
        condition: advancedFormula(
          `greater_than(length(get('previous_node.${listRows.id}')), 0)`
        ),
      },
    })
  }
}
