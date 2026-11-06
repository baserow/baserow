import CoreHTTPTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPTriggerServiceForm'
import CoreInboundEmailTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreInboundEmailTriggerServiceForm'
import CoreManualTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreManualTriggerServiceForm'
import {
  DataSourceServiceTypeMixin,
  getFilesGroup,
  getHTTPGroup,
  getWorkflowGroup,
  ServiceType,
  TriggerServiceTypeMixin,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import CoreHTTPRequestServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPRequestServiceForm'
import CoreSMTPEmailServiceForm from '@baserow/modules/integrations/core/components/services/CoreSMTPEmailServiceForm'
import CoreRouterServiceForm from '@baserow/modules/integrations/core/components/services/CoreRouterServiceForm'
import CoreGotoServiceForm from '@baserow/modules/integrations/core/components/services/CoreGotoServiceForm'
import CoreIteratorServiceForm from '@baserow/modules/integrations/core/components/services/CoreIteratorServiceForm'
import CoreCSVFileReaderServiceForm from '@baserow/modules/integrations/core/components/services/CoreCSVFileReaderServiceForm'
import CorePeriodicTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CorePeriodicTriggerServiceForm.vue'
import CoreStartWorkflowServiceForm from '@baserow/modules/integrations/core/components/services/CoreStartWorkflowServiceForm.vue'
import { SMTPIntegrationType } from '@baserow/modules/integrations/core/integrationTypes'
import CoreResponseServiceForm from '@baserow/modules/integrations/core/components/services/CoreResponseServiceForm.vue'
import CoreHTTPDataSourceServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPDataSourceServiceForm'
import {
  HTTP_DATA_SOURCE_MAX_RESULT_LIMIT,
  HTTP_DATA_SOURCE_TYPE,
} from '@baserow/modules/integrations/core/enums'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import { ToTipTapVisitor } from '@baserow/modules/core/formula/tiptap/toTipTapVisitor'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'
import { toFormulaStringLiteral } from '@baserow/modules/core/formula'
import { uuid } from '@baserow/modules/core/utils/string'

/**
 * The text of a formula as its input shows it: the text in simple mode, with
 * each data reference as `{path}`, and the formula itself in advanced mode.
 */
const getFormulaText = (app, { formula, mode }) => {
  if (mode === 'advanced') {
    return formula
  }
  const toText = (node) => {
    if (node.type === 'text') {
      return node.text.replaceAll('\u200B', '')
    }
    if (node.attrs?.path) {
      return `{${node.attrs.path}}`
    }
    if (node.type === 'newLine' || node.type === 'hardBreak') {
      return ' '
    }
    return (node.content || []).map(toText).join('')
  }
  try {
    const tree = parseBaserowFormula(formula, false)
    const functions = new RuntimeFunctionCollection(app.$registry)
    return toText(new ToTipTapVisitor(functions).visit(tree))
  } catch {
    return formula
  }
}

export class CoreHTTPRequestServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'http_request'
  }

  get icon() {
    return 'iconoir-cloud-upload'
  }

  get group() {
    return getHTTPGroup(this.app)
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreHTTPRequest')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreHTTPRequestDescription')
  }

  getErrorMessage({ service }) {
    // We check undefined because the url is not returned in public mode the
    // property is just ignored
    if (
      service !== undefined &&
      service.url !== undefined &&
      !service.url.formula
    ) {
      return this.app.$i18n.t('serviceType.errorUrlMissing')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreHTTPRequestServiceForm
  }

  getOrder() {
    return 5
  }
}

export class CoreSMTPEmailServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'smtp_email'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreSMTPEmail')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreSMTPEmailDescription')
  }

  get icon() {
    return 'iconoir-send-mail'
  }

  get integrationType() {
    return this.app.$registry.get('integration', SMTPIntegrationType.getType())
  }

  getErrorMessage({ service }) {
    if (
      service === undefined ||
      // This case happens in a published application. We don't want to check
      // the validity in that case.
      service.use_instance_smtp_settings === undefined
    ) {
      return null
    }

    if (!service.use_instance_smtp_settings && !service.integration_id) {
      return this.app.$i18n.t('serviceType.errorNoIntegrationSelected')
    }

    if (
      !service.use_instance_smtp_settings &&
      service.from_email !== undefined &&
      !service.from_email.formula
    ) {
      return this.app.$i18n.t('serviceType.errorFromEmailMissing')
    }

    if (service.to_emails !== undefined && !service.to_emails.formula?.trim()) {
      return this.app.$i18n.t('serviceType.errorToEmailsMissing')
    }

    return super.getErrorMessage({ service })
  }

  /**
   * An email answers with whether it went out and nothing else, so the shape
   * is known before the service is saved. Without it an action added in an
   * editor is missing from the next action's explorer until a save and
   * reopen. Matches what the backend builds for the saved service.
   */
  getDataSchema(service) {
    return (
      service.schema || {
        type: 'object',
        properties: {
          success: {
            type: 'boolean',
            title: 'Success',
            description: 'Whether the email was sent successfully',
          },
        },
      }
    )
  }

  get formComponent() {
    return CoreSMTPEmailServiceForm
  }

  getOrder() {
    return 6
  }
}

export class CoreRouterServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'router'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreRouter')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreRouterDescription')
  }

  get icon() {
    return 'iconoir-git-fork'
  }

  get group() {
    return getWorkflowGroup(this.app)
  }

  getEdgeErrorMessage(edge) {
    if (!edge.label.length) {
      return this.app.$i18n.t('serviceType.coreRouterEdgeLabelRequired')
    } else if (!edge.condition.formula) {
      return this.app.$i18n.t('serviceType.coreRouterEdgeConditionRequired')
    }
    return null
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }
    if (!service.edges?.length) {
      return this.app.$i18n.t('serviceType.coreRouterEdgesRequired')
    }
    for (const edge of service.edges) {
      const errorMessage = this.getEdgeErrorMessage(edge)
      if (errorMessage) {
        return errorMessage
      }
    }
    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreRouterServiceForm
  }

  getOrder() {
    return 7
  }
}

export class CoreGotoServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'goto'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreGoto')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreGotoDescription')
  }

  get icon() {
    return 'iconoir-long-arrow-up-right'
  }

  get group() {
    return getWorkflowGroup(this.app)
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }
    if (!service.destination_service_id) {
      return this.app.$i18n.t('serviceType.coreGotoDestinationRequired')
    }
    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreGotoServiceForm
  }

  getOrder() {
    return 10
  }
}

export class CoreHTTPTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'http_trigger'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreHTTPTrigger')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreHTTPTriggerDescription')
  }

  get formComponent() {
    return CoreHTTPTriggerServiceForm
  }

  get icon() {
    return 'iconoir-globe'
  }

  get group() {
    return getHTTPGroup(this.app)
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  getOrder() {
    return 8
  }
}

export class CoreInboundEmailTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'email_trigger'
  }

  get name() {
    return this.app.$i18n.t('serviceType.inboundEmailTrigger')
  }

  get description() {
    return this.app.$i18n.t('serviceType.inboundEmailTriggerDescription')
  }

  get formComponent() {
    return CoreInboundEmailTriggerServiceForm
  }

  get icon() {
    return 'iconoir-mail'
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  /**
   * The sample data is a received email, so the sample data modal offers an
   * HTML preview tab next to the JSON payload.
   */
  getSampleDataContentType(service) {
    return 'html'
  }

  getSampleDataHtml(service) {
    return service.sample_data?.data?.body_html || null
  }

  getOrder() {
    return 8.5
  }
}

export class CoreManualTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'manual'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreManualTrigger')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreManualTriggerDescription')
  }

  get icon() {
    return 'iconoir-play'
  }

  get formComponent() {
    return CoreManualTriggerServiceForm
  }

  canBeImmediatelyDispatched(service) {
    return true
  }

  getDataSchema(service) {
    return service.schema
  }

  getOrder() {
    return 9
  }
}

export class CoreIteratorServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'iterator'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreIteration')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreIterationDescription')
  }

  get icon() {
    return 'iconoir-repeat'
  }

  get group() {
    return getWorkflowGroup(this.app)
  }

  returnsList(service) {
    return true
  }

  getErrorMessage({ service }) {
    if (!service?.source?.formula) {
      return this.app.$i18n.t('serviceType.errorIterationSourceMissing')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreIteratorServiceForm
  }

  getOrder() {
    return 5
  }
}

export class CoreCSVFileReaderServiceType extends DataSourceServiceTypeMixin(
  WorkflowActionServiceTypeMixin(ServiceType)
) {
  static getType() {
    return 'csv_file_reader'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreCSVFileReader')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreCSVFileReaderDescription')
  }

  get icon() {
    return 'iconoir-page'
  }

  get group() {
    return getFilesGroup(this.app)
  }

  returnsList(service) {
    return true
  }

  get hiddenInDataSourcePicker() {
    return true
  }

  getRecordName(service, record) {
    return record?.name || record?.id || ''
  }

  getIdProperty(service, record) {
    return record?.id != null ? 'id' : '_id'
  }

  getResult(service, data) {
    return data.results
  }

  getErrorMessage({ service }) {
    if (service?.input_type === undefined && service?.file === undefined) {
      // The service is not loaded yet, or we are in preview or published mode
      return super.getErrorMessage({ service })
    }

    if (service?.input_type === 'content') {
      if (!service?.csv?.formula) {
        return this.app.$i18n.t('serviceType.errorCSVContentMissing')
      }
    } else if (!service?.file?.formula) {
      return this.app.$i18n.t('serviceType.errorCSVFileMissing')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreCSVFileReaderServiceForm
  }

  getOrder() {
    return 6
  }
}

/**
 * An HTTP request used as a data source. It always sends a GET, and its result
 * is the JSON body of the response. Whether the body is a single record or a
 * list of them is the type itself: this one, or the list type below, which
 * the picker shows as this same entry.
 */
export class CoreHTTPDataSourceServiceType extends DataSourceServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return HTTP_DATA_SOURCE_TYPE
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreHTTPDataSource')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreHTTPDataSourceDescription')
  }

  get icon() {
    return 'iconoir-globe'
  }

  get group() {
    return getHTTPGroup(this.app)
  }

  get canBeTested() {
    return true
  }

  get hasOwnTestButton() {
    return true
  }

  getDescription(service, application) {
    const url = service.url?.formula
      ? getFormulaText(this.app, service.url).trim()
      : ''
    return url ? `GET ${url}` : this.name
  }

  getErrorMessage({ service }) {
    // The url isn't returned in public mode, where nothing is checked.
    if (service?.url === undefined) {
      return super.getErrorMessage({ service })
    }

    if (!service.url.formula) {
      return this.app.$i18n.t('serviceType.errorUrlMissing')
    }

    // The schema is built from the response of the last test.
    if (!service.schema) {
      return this.app.$i18n.t('serviceType.errorHTTPDataSourceNotTested')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  /**
   * The response of the last test, or undefined when there is none.
   */
  getSampleResponse(service) {
    const sample = this.getSampleData(service)
    if (!sample || sample._error || !('data' in sample)) {
      return undefined
    }
    // A list keeps the response next to the records read from it.
    return this.returnsList(service) ? sample.data?.response : sample.data
  }

  returnsList(service) {
    return Boolean(service?.returns_list)
  }

  getRecordName(service, record) {
    return record?.name ?? record?.id ?? record?._id ?? ''
  }

  getIdProperty(service, record) {
    // Records are given their position when not all of them have an `id`. It
    // identifies them then, as an `id` could be the same as another position.
    return record?._id != null ? '_id' : 'id'
  }

  parseRecordId(value) {
    // An API's ids are as often strings as numbers.
    return value === '' || value === null || value === undefined
      ? null
      : `${value}`
  }

  getRecordIdDataType(service) {
    return 'string'
  }

  getMaxResultLimit(service) {
    return HTTP_DATA_SOURCE_MAX_RESULT_LIMIT
  }

  /**
   * A column per property of the records holding a plain value. Nested objects
   * and lists can't be shown as text, and a name with a dot can't be a path.
   */
  getDefaultCollectionFields(service) {
    const properties = this.getDataSchema(service)?.items?.properties || {}
    return Object.entries(properties)
      .map(([name, property]) => [
        name,
        [property.type].flat().find((type) => type !== 'null'),
      ])
      .filter(
        ([name, type]) =>
          name !== '_id' &&
          !name.includes('.') &&
          ['string', 'number', 'integer', 'boolean'].includes(type)
      )
      .map(([name, type]) => ({
        id: uuid(), // Temporary id
        name,
        type: type === 'boolean' ? 'boolean' : 'text',
        value: {
          formula: `get(${toFormulaStringLiteral(`current_record.${name}`)})`,
        },
      }))
  }

  getResult(service, data) {
    return this.returnsList(service)
      ? data.results
      : super.getResult(service, data)
  }

  get formComponent() {
    return CoreHTTPDataSourceServiceForm
  }

  getOrder() {
    return 5
  }
}

export class CoreStartWorkflowServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'start_workflow'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreStartWorkflow')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreStartWorkflowDescription')
  }

  get icon() {
    return 'iconoir-play'
  }

  get group() {
    return getWorkflowGroup(this.app)
  }

  getWorkflow(
    workflowId,
    workspace = this.app.$store.getters['workspace/getSelected']
  ) {
    if (!workspace?.id || !workflowId) {
      return null
    }

    const automations = this.app.$store.getters[
      'application/getAllOfWorkspace'
    ](workspace).filter((application) => application.type === 'automation')

    return automations
      .flatMap((automation) =>
        this.app.$store.getters['automationWorkflow/getWorkflows'](automation)
      )
      .find((workflow) => workflow.id === workflowId)
  }

  getErrorMessage({ service }) {
    if (service !== undefined && service.workflow_id === null) {
      return this.app.$i18n.t('serviceType.errorNoWorkflowSelected')
    }

    const workflow = this.getWorkflow(service?.workflow_id)
    if (workflow && !workflow.immediate_dispatch) {
      return this.app.$i18n.t('serviceType.errorWorkflowNotImmediateDispatch')
    }

    return super.getErrorMessage({ service })
  }

  get formComponent() {
    return CoreStartWorkflowServiceForm
  }

  getDataSchema(service) {
    return service.schema
  }

  getOrder() {
    return 8
  }
}

export class CoreResponseServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'response'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreResponse')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreResponseDescription')
  }

  get icon() {
    return 'iconoir-reply'
  }

  get group() {
    return getWorkflowGroup(this.app)
  }

  get formComponent() {
    return CoreResponseServiceForm
  }

  getDataSchema(service) {
    return service.schema
  }

  getErrorMessage(params) {
    const { service } = params
    // The service is undefined while a node is being created optimistically
    // and the API has not responded yet.
    if (service === undefined) {
      return super.getErrorMessage(params)
    }
    const isNoContentResponse =
      service.status_code?.mode === 'raw' &&
      service.status_code.formula === '204'
    if (
      !isNoContentResponse &&
      service.body_type === 'json' &&
      !service.body?.formula?.trim()
    ) {
      return this.app.$i18n.t('serviceType.errorResponseBodyMissing')
    }
    return super.getErrorMessage(params)
  }

  getOrder() {
    return 9
  }
}

export class CorePeriodicTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'periodic'
  }

  get name() {
    return this.app.$i18n.t('serviceType.corePeriodic')
  }

  get description() {
    return this.app.$i18n.t('serviceType.corePeriodicDescription')
  }

  get formComponent() {
    return CorePeriodicTriggerServiceForm
  }

  get icon() {
    return 'iconoir-timer'
  }

  canBeImmediatelyDispatched(service) {
    return true
  }

  getDataSchema(service) {
    return service.schema
  }

  getErrorMessage({ service }) {
    if (!service?.interval) {
      return this.app.$i18n.t('serviceType.corePeriodicErrorIntervalMissing')
    }
    return super.getErrorMessage({ service })
  }
}
