import { Registerable } from '@baserow/modules/core/registry'
import {
  ActionNodeTypeMixin,
  TriggerNodeTypeMixin,
  UtilityNodeMixin,
  containerNodeTypeMixin,
} from '@baserow/modules/automation/nodeTypeMixins'
import {
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowUpdateRowWorkflowServiceType,
  LocalBaserowDeleteRowWorkflowServiceType,
  LocalBaserowRowsCreatedTriggerServiceType,
  LocalBaserowRowsDeletedTriggerServiceType,
  LocalBaserowRowsUpdatedTriggerServiceType,
  LocalBaserowGetRowServiceType,
  LocalBaserowListRowsServiceType,
  LocalBaserowAggregateRowsServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'
import slackIntegration from '@baserow/modules/integrations/slack/assets/images/slack.svg'
import localBaserowIntegration from '@baserow/modules/integrations/localBaserow/assets/images/localBaserowIntegration.svg'
import {
  CoreHTTPRequestServiceType,
  CoreRouterServiceType,
  CoreSMTPEmailServiceType,
  CoreHTTPTriggerServiceType,
  CoreIteratorServiceType,
} from '@baserow/modules/integrations/core/serviceTypes'
import { AIAgentServiceType } from '@baserow/modules/integrations/ai/serviceTypes'
import { uuid } from '@baserow/modules/core/utils/string'
import { SlackWriteMessageServiceType } from '@baserow/modules/integrations/slack/serviceTypes'

export class NodeType extends Registerable {
  /**
   * The display name of the node type, we use this value
   * in create/update node lists.
   * The name is derived from the service type's name.
   * @returns {string} - The display name for the node.
   */
  get name() {
    return this.serviceType.name
  }

  /**
   * If the workflow designer doesn't provide a `label` for the node,
   * this method is used to generate a default label.
   * By default, it returns the node type's name.
   * @param node - The node for which the default label is being generated.
   * @returns {string} - The default label for the node.
   */
  getDefaultLabel({ node }) {
    return this.name
  }

  /**
   * The display label of the node type, we use this value
   * in the editor when rendering the node.
   * @returns {string} - The display label for the node.
   */
  getLabel({ automation, node }) {
    return node.label || this.getDefaultLabel({ automation, node })
  }

  /**
   * Returns the text to be displayed on the graph just before the node.
   */
  getBeforeLabel({ workflow, node }) {
    return this.app.i18n.t('workflowNode.beforeLabelAction')
  }

  /**
   * The node type's description.
   * The description is derived from the service type's description.
   * @returns {string} - The node's description.
   */
  get description() {
    return this.serviceType.description
  }

  /**
   * New nodes must implement this method to return their
   * specific service type.
   * @throws {Error} If the method is not implemented.
   */
  get serviceType() {
    throw new Error('This method must be implemented')
  }

  /**
   * The icon which is shown inside the editor's node.
   * @returns {string} - The node's icon class.
   */

  get iconClass() {
    return this.serviceType.icon
  }

  /**
   * The node type's image, which will be displayed in dropdowns.
   * @returns - The node's image.
   */
  get image() {
    return null
  }

  /**
   * The node type's editor component. Not yet implemented.
   * @returns {object|null} - The node's editor component.
   */
  get component() {
    return null
  }

  /**
   * The node type's form component.
   * The component is derived from the service type's form component.
   * @returns {object} - The node's form component.
   */
  get formComponent() {
    return this.serviceType.formComponent
  }

  /**
   * Whether this node type can be moved around the workflow. By default,
   * all nodes can be moved. This can be overridden by the node type
   * to prevent moving.
   * @returns {boolean} - Whether the node can be moved.
   */
  get isFixed() {
    return false
  }

  /**
   * Allow to hook into default values for this node type at node creation.
   * @param {object} values the current values for the node to create.
   * @returns an object containing values updated with the default values.
   */
  getDefaultValues(values) {
    return values
  }

  /**
   * Returns whether the node is in-error or not.
   * By default, this is derived from the service type's `isInError`
   * method, but can be overridden by the node type.
   * @returns {boolean} - Whether the properties are in-error.
   */
  isInError({ service }) {
    return this.serviceType.isInError({ service })
  }

  /**
   * Returns the error message we should show when the node is in-error.
   * By default, this is derived from the service type's `getErrorMessage`
   * method, but can be overridden by the node type.
   * @param {object} service - The service of the node.
   * @param {object} node - The node for which the
   *  error message is being retrieved.
   * @returns {string} - The error message.
   */
  getErrorMessage({ service, node }) {
    return this.serviceType.getErrorMessage({ service })
  }

  /**
   * Returns whether this individual node is allowed to be deleted.
   * By default, all nodes (except triggers) are allowed to be deleted.
   * This can be overridden by the node type to prevent deletion.
   * @param {object} workflow - The workflow the node belongs to.
   * @param {object} node - The node for which the deletability is being checked.
   * @returns {boolean} - Whether the node is allowed to be deleted.
   */
  isDeletable({ workflow, node }) {
    return Boolean(this.getDeleteErrorMessage({ workflow, node }))
  }

  /**
   * Returns whether the given node can be duplicated.
   */
  isDuplicable({ workflow, node }) {
    return true
  }

  /**
   * Returns the error message we should show when a node cannot be deleted.
   * By default, this method is empty, but can be overridden by the node type
   * to provide a custom deletion message.
   * @param {object} workflow - The workflow the node belongs to.
   * @param {object} node - The node for which the deletion message is being retrieved.
   * @returns {string} - The message
   */
  getDeleteErrorMessage({ workflow, node }) {
    return ''
  }

  /**
   * Returns whether this individual node is allowed to be replaced.
   * By default, all nodes are allowed to be replaced.
   * This can be overridden by the node type to prevent replacement.
   * @param {object} workflow - The workflow the node belongs to.
   * @param {object} node - The node for which the replaceability is being checked.
   * @returns {boolean} - Whether the node is allowed to be replaced.
   */
  isReplaceable({ workflow, node }) {
    return Boolean(this.getReplaceErrorMessage({ workflow, node }))
  }

  /**
   * Returns the error message we should show when a node cannot be replaced.
   * By default, this method is empty, but can be overridden by the node type
   * to provide a custom replacement message.
   * @param {object} workflow - The workflow the node belongs to.
   * @param {object} node - The node for which the replacement message is being retrieved.
   * @returns {string} - The message.
   */
  getReplaceErrorMessage({ workflow, node }) {
    return ''
  }

  /**
   * Returns this node's data type, used by the `getDataSchema` method
   * to inform the schema about what kind of data type this node returns.
   *
   * @returns {string} - The data type of the node, which is 'object' by default.
   */
  get dataType() {
    return 'object'
  }

  /**
   * Generates the data schema for the node, used by the data provider.
   * Constructed by retrieving the service schema for this node's service.
   * @param automation - The automation the node belongs to.
   * @param node - The node for which the data schema is being generated.
   * @returns {object} - The data schema for the node.
   */
  getDataSchema({ automation, node }) {
    if (!node.service) {
      return null
    }
    const serviceSchema = this.serviceType.getDataSchema(node.service)
    if (serviceSchema) {
      return {
        ...serviceSchema,
        title: this.getLabel({ automation, node }),
      }
    }
    return null
  }

  /**
   * Returns the sample data for this node.
   */
  getSampleData({ service }) {
    if (!service) {
      return null
    }
    return this.serviceType.getSampleData(service)
  }

  getEdges({ node }) {
    return [{ uid: '', label: '' }]
  }
}

export class LocalBaserowNodeType extends NodeType {
  /**
   * Responsible for returning contextual data for a node label template.
   * At the moment we only refer to the table name.
   *
   * @param automation - the automation the node belongs to.
   * @param node - The node for which the label context is being retrieved.
   * @returns {object} - An object containing the table name.
   */
  getLabelContext({ automation, node }) {
    const integration = this.app.store.getters[
      'integration/getIntegrationById'
    ](automation, node.service?.integration_id)
    const databases = integration?.context_data?.databases || []
    const tableSelected = databases
      .map((database) => database.tables)
      .flat()
      .find(({ id }) => id === node.service.table_id)

    return { tableName: tableSelected?.name }
  }

  /**
   * If the workflow designer doesn't provide a `label` for the node,
   * this method is used to generate a default label.
   * @param automation - The automation the node belongs to.
   * @param node - The node for which the default label is being generated.
   * @returns {string} - The default label for the node.
   */
  getDefaultLabel({ automation, node }) {
    const { tableName } = this.getLabelContext({ automation, node })
    return tableName
      ? this.app.i18n.t(this.labelTemplateName, { tableName })
      : this.name
  }

  get image() {
    return localBaserowIntegration
  }
}

export class LocalBaserowSignalTriggerType extends LocalBaserowNodeType {
  /**
   * All Local Baserow signal triggers return an array of rows,
   * so we override the `dataType` method to return 'array'.
   * @returns {string} - The data type of the node, which is 'array'.
   */
  get dataType() {
    return 'array'
  }
}

export class LocalBaserowRowsCreatedTriggerNodeType extends TriggerNodeTypeMixin(
  LocalBaserowSignalTriggerType
) {
  static getType() {
    return 'local_baserow_rows_created'
  }

  getOrder() {
    return 1
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowRowsCreatedLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowRowsCreatedTriggerServiceType.getType()
    )
  }
}

export class LocalBaserowRowsUpdatedTriggerNodeType extends TriggerNodeTypeMixin(
  LocalBaserowSignalTriggerType
) {
  static getType() {
    return 'local_baserow_rows_updated'
  }

  getOrder() {
    return 2
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowRowsUpdatedLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowRowsUpdatedTriggerServiceType.getType()
    )
  }
}

export class LocalBaserowRowsDeletedTriggerNodeType extends TriggerNodeTypeMixin(
  LocalBaserowSignalTriggerType
) {
  static getType() {
    return 'local_baserow_rows_deleted'
  }

  getOrder() {
    return 3
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowRowsDeletedLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowRowsDeletedTriggerServiceType.getType()
    )
  }
}

export class CorePeriodicTriggerNodeType extends TriggerNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'periodic'
  }

  getOrder() {
    return 4
  }

  get name() {
    return this.app.i18n.t('nodeType.periodicTriggerLabel')
  }

  get serviceType() {
    return this.app.$registry.get('service', 'periodic')
  }

  getDefaultLabel({ node }) {
    if (!node.service) {
      return this.name
    }

    const intervalLabels = {
      MINUTE: this.app.i18n.t('periodicForm.everyMinute', {
        minute: node.service.minute,
      }),
      HOUR: this.app.i18n.t('periodicForm.everyHour'),
      DAY: this.app.i18n.t('periodicForm.everyDay'),
      WEEK: this.app.i18n.t('periodicForm.everyWeek'),
      MONTH: this.app.i18n.t('periodicForm.everyMonth'),
    }

    return intervalLabels[node.service.interval] || this.name
  }
}

export class CoreHTTPTriggerNodeType extends TriggerNodeTypeMixin(NodeType) {
  static getType() {
    return 'http_trigger'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreHTTPTrigger')
  }

  get description() {
    return this.app.i18n.t('serviceType.coreHTTPTriggerDescription')
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      CoreHTTPTriggerServiceType.getType()
    )
  }

  getOrder() {
    return 4
  }

  getDefaultLabel({ automation, node }) {
    return this.app.i18n.t('serviceType.coreHTTPTrigger')
  }
}

export class LocalBaserowCreateRowActionNodeType extends ActionNodeTypeMixin(
  LocalBaserowNodeType
) {
  static getType() {
    return 'local_baserow_create_row'
  }

  getOrder() {
    return 1
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowCreateRowLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowWorkflowServiceType.getType()
    )
  }
}

export class LocalBaserowUpdateRowActionNodeType extends ActionNodeTypeMixin(
  LocalBaserowNodeType
) {
  static getType() {
    return 'local_baserow_update_row'
  }

  getOrder() {
    return 2
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowUpdateRowLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowUpdateRowWorkflowServiceType.getType()
    )
  }
}

export class LocalBaserowDeleteRowActionNodeType extends ActionNodeTypeMixin(
  LocalBaserowNodeType
) {
  static getType() {
    return 'local_baserow_delete_row'
  }

  getOrder() {
    return 3
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowDeleteRowLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowDeleteRowWorkflowServiceType.getType()
    )
  }
}

export class LocalBaserowGetRowActionNodeType extends ActionNodeTypeMixin(
  LocalBaserowNodeType
) {
  static getType() {
    return 'local_baserow_get_row'
  }

  getOrder() {
    return 4
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowGetRowLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowGetRowServiceType.getType()
    )
  }
}

export class LocalBaserowListRowsActionNodeType extends ActionNodeTypeMixin(
  LocalBaserowNodeType
) {
  static getType() {
    return 'local_baserow_list_rows'
  }

  getOrder() {
    return 5
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowListRowsLabel'
  }

  get dataType() {
    return 'array'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowListRowsServiceType.getType()
    )
  }
}

export class LocalBaserowAggregateRowsActionNodeType extends ActionNodeTypeMixin(
  LocalBaserowNodeType
) {
  static getType() {
    return 'local_baserow_aggregate_rows'
  }

  getOrder() {
    return 6
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowAggregateRowsLabel'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowAggregateRowsServiceType.getType()
    )
  }
}

export class CoreHttpRequestNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'http_request'
  }

  getOrder() {
    return 7
  }

  get name() {
    return this.app.i18n.t('nodeType.httpRequestLabel')
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      CoreHTTPRequestServiceType.getType()
    )
  }
}

export class CoreIteratorNodeType extends containerNodeTypeMixin(
  ActionNodeTypeMixin(UtilityNodeMixin(NodeType))
) {
  static getType() {
    return 'iterator'
  }

  getOrder() {
    return 8
  }

  get name() {
    return this.app.i18n.t('nodeType.iterationLabel')
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreIteratorServiceType.getType())
  }

  /**
   * Responsible for checking if the router node can be deleted. It can't be
   * if it has output nodes connected to its edges.
   * @param workflow - The workflow the router belongs to.
   * @param node - The router node for which the deletability is being checked.
   * @returns {string} - An error message if the router cannot be deleted.
   */
  getDeleteErrorMessage({ workflow, node }) {
    const children = this.app.store.getters[
      'automationWorkflowNode/getChildren'
    ](workflow, node)
    const count = children.length
    if (count) {
      return this.app.i18n.t('nodeType.iteratorWithChildrenNodesDeleteError', {
        count,
      })
    }
    return ''
  }

  getBeforeLabel({ workflow, node, position, output }) {
    if (position === 'child') {
      return this.app.i18n.t('workflowNode.beforeLabelRepeat')
    }

    return super.getBeforeLabel({ workflow, node, position, output })
  }

  /**
   * Responsible for checking if the router node can be replaced. It can't be
   * if it has output nodes connected to its edges.
   * @param workflow - The workflow the router belongs to.
   * @param node - The router node for which the replaceability is being checked.
   * @returns {string} - An error message if the router cannot be replaced.
   */
  getReplaceErrorMessage({ workflow, node }) {
    const children = this.app.store.getters[
      'automationWorkflowNode/getChildren'
    ](workflow, node)
    const count = children.length
    if (count) {
      return this.app.i18n.t('nodeType.iteratorWithChildrenNodesReplaceError', {
        count,
      })
    }
    return ''
  }

  isDuplicable({ workflow, node }) {
    return false
  }
}

export class CoreSMTPEmailNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'smtp_email'
  }

  getOrder() {
    return 8
  }

  get name() {
    return this.app.i18n.t('nodeType.smtpEmailLabel')
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreSMTPEmailServiceType.getType())
  }
}

export class CoreRouterNodeType extends ActionNodeTypeMixin(
  UtilityNodeMixin(NodeType)
) {
  static getType() {
    return 'router'
  }

  /**
   * Router nodes cannot be moved around the workflow, due to complications
   * with managing their output nodes. This will be improved in the future,
   * but for now, this node type is fixed.
   * @returns {boolean} - Whether the node can be moved.
   */
  get isFixed() {
    return true
  }

  getBeforeLabel({ workflow, node, position, output }) {
    if (output.length > 0) {
      return this.app.i18n.t('workflowNode.beforeLabelCondition')
    }
    return this.app.i18n.t('workflowNode.beforeLabelConditionDefault')
  }

  getOrder() {
    return 9
  }

  getDefaultLabel({ node }) {
    if (!node.service) return this.name
    return node.service.edges.length
      ? this.app.i18n.t('nodeType.routerLabel', {
          edgeCount: this.getEdges({ node }).length,
        })
      : this.name
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreRouterServiceType.getType())
  }

  /**
   * Allow to hook into default values for this node type at node creation.
   * The fallback edge is deliberately omitted as the goal is to replicate
   * what the API returns when creating a router node.
   * @param {object} values the current values for the node to create.
   * @returns an object containing values updated with the default values.
   */
  getDefaultValues(values) {
    return {
      ...values,
      service: {
        edges: [
          {
            uid: uuid(),
            order: 0,
            condition: '',
            label: this.app.i18n.t('routerForm.edgeDefaultName'),
          },
        ],
      },
    }
  }

  /**
   * Responsible for checking if the router node can be deleted. It can't be
   * if it has output nodes connected to its edges.
   * @param workflow - The workflow the router belongs to.
   * @param node - The router node for which the deletability is being checked.
   * @returns {string} - An error message if the router cannot be deleted.
   */
  getDeleteErrorMessage({ workflow, node }) {
    const outputCount = this.getOutputNodes({ workflow, router: node }).length
    if (outputCount) {
      return this.app.i18n.t('nodeType.routerWithOutputNodesDeleteError', {
        outputCount,
      })
    }
    return ''
  }

  /**
   * Responsible for checking if the router node can be replaced. It can't be
   * if it has output nodes connected to its edges.
   * @param workflow - The workflow the router belongs to.
   * @param node - The router node for which the replaceability is being checked.
   * @returns {string} - An error message if the router cannot be replaced.
   */
  getReplaceErrorMessage({ workflow, node }) {
    const outputCount = this.getOutputNodes({ workflow, router: node }).length
    if (outputCount) {
      return this.app.i18n.t('nodeType.routerWithOutputNodesReplaceError', {
        outputCount,
      })
    }
    return ''
  }

  /**
   * Responsible for finding the output nodes coming out of this router's edges.
   * @param workflow - The workflow the router belongs to.
   * @param router - The router node for which the output nodes are being retrieved.
   * @returns {Array} - An array of output nodes that are connected to the router's edges.
   */
  getOutputNodes({ workflow, router }) {
    return this.app.store.getters['automationWorkflowNode/getNextNodes'](
      workflow,
      router
    )
  }

  /**
   * Responsible for retrieving the edges of the router node. This will include
   * the user-created edges as well as a fallback edge with an empty uid.
   * @param node - The router node for which the edges are being retrieved.
   * @returns {array} - An array of edges, each with a uid and label.
   */
  getEdges({ node }) {
    if (!node.service) return []
    return [
      ...node.service.edges,
      {
        uid: '', // The fallback edge has no uid.
        condition: '',
        label:
          node.service.default_edge_label ||
          this.app.i18n.t('nodeType.routerDefaultEdgeLabelFallback'),
      },
    ]
  }

  isDuplicable({ workflow, node }) {
    return false
  }
}

export class AIAgentActionNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'ai_agent'
  }

  get name() {
    return this.app.i18n.t('nodeType.aiAgent')
  }

  get iconClass() {
    return 'iconoir-sparks'
  }

  get serviceType() {
    return this.app.$registry.get('service', AIAgentServiceType.getType())
  }

  getOrder() {
    return 8
  }
}

export class SlackWriteMessageNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'slack_write_message'
  }

  getOrder() {
    return 8
  }

  get iconClass() {
    return ''
  }

  get image() {
    return slackIntegration
  }

  get name() {
    return this.app.i18n.t('nodeType.slackWriteMessageName')
  }

  getDefaultLabel({ node }) {
    if (!node.service) return this.name
    return node.service.channel.length
      ? this.app.i18n.t('nodeType.slackWriteMessageLabel', {
          channel: node.service.channel,
        })
      : this.name
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      SlackWriteMessageServiceType.getType()
    )
  }
}
