import {
  ExternalServiceType,
  formulaField,
  integerField,
} from '@baserow/modules/integrations/common/externalServiceType'
import { GoogleIntegrationType } from '@baserow/modules/integrations/google/integrationTypes'

class GoogleServiceType extends ExternalServiceType {
  static get integrationTypeClass() {
    return GoogleIntegrationType
  }
}

const emailFields = [
  formulaField('to_emails', 'toEmails', {
    required: true,
    placeholder: 'emailsPlaceholder',
    help: 'emailsHelp',
  }),
  formulaField('cc_emails', 'ccEmails', { placeholder: 'emailsPlaceholder' }),
  formulaField('bcc_emails', 'bccEmails', { placeholder: 'emailsPlaceholder' }),
  formulaField('subject', 'subject', { required: true }),
  formulaField('body', 'body', { required: true, help: 'plainTextBodyHelp' }),
]

const googleCalendarField = formulaField('calendar_id', 'googleCalendarId', {
  help: 'googleCalendarIdHelp',
})

const eventFields = (summaryName, descriptionName, required) => [
  formulaField(summaryName, 'eventTitle', { required }),
  formulaField(descriptionName, 'eventDescription'),
  formulaField('location', 'eventLocation'),
  formulaField('start', 'eventStart', { required, help: 'eventTimeHelp' }),
  formulaField('end', 'eventEnd', { required, help: 'eventTimeHelp' }),
  formulaField('time_zone', 'eventTimeZone', {
    placeholder: 'eventTimeZonePlaceholder',
    help: 'eventTimeZoneHelp',
  }),
  formulaField('attendees', 'eventAttendees', {
    placeholder: 'emailsPlaceholder',
  }),
]

export class GmailSendEmailServiceType extends GoogleServiceType {
  static getType() {
    return 'gmail_send_email'
  }

  static get i18nKey() {
    return 'gmailSendEmail'
  }

  get icon() {
    return 'iconoir-send-mail'
  }

  get formFields() {
    return emailFields
  }

  getOrder() {
    return 30
  }
}

export class GoogleCalendarCreateEventServiceType extends GoogleServiceType {
  static getType() {
    return 'google_calendar_create_event'
  }

  static get i18nKey() {
    return 'googleCalendarCreateEvent'
  }

  get icon() {
    return 'iconoir-calendar-plus'
  }

  get formFields() {
    return [googleCalendarField, ...eventFields('summary', 'description', true)]
  }

  getOrder() {
    return 31
  }
}

export class GoogleCalendarUpdateEventServiceType extends GoogleServiceType {
  static getType() {
    return 'google_calendar_update_event'
  }

  static get i18nKey() {
    return 'googleCalendarUpdateEvent'
  }

  get icon() {
    return 'iconoir-edit-pencil'
  }

  get formFields() {
    return [
      googleCalendarField,
      formulaField('event_id', 'eventId', {
        required: true,
        help: 'eventIdHelp',
      }),
      ...eventFields('summary', 'description', false),
    ]
  }

  getOrder() {
    return 32
  }
}

export class GoogleCalendarDeleteEventServiceType extends GoogleServiceType {
  static getType() {
    return 'google_calendar_delete_event'
  }

  static get i18nKey() {
    return 'googleCalendarDeleteEvent'
  }

  get icon() {
    return 'iconoir-calendar-minus'
  }

  get formFields() {
    return [
      googleCalendarField,
      formulaField('event_id', 'eventId', {
        required: true,
        help: 'eventIdHelp',
      }),
    ]
  }

  getOrder() {
    return 33
  }
}

export class GoogleCalendarListEventsServiceType extends GoogleServiceType {
  static getType() {
    return 'google_calendar_list_events'
  }

  static get i18nKey() {
    return 'googleCalendarListEvents'
  }

  get icon() {
    return 'iconoir-calendar'
  }

  get formFields() {
    return [
      googleCalendarField,
      formulaField('time_min', 'eventsFrom', { help: 'eventsWindowHelp' }),
      formulaField('time_max', 'eventsUntil', { help: 'eventsWindowHelp' }),
      formulaField('query', 'eventsQuery', { help: 'eventsQueryHelp' }),
      integerField('max_results', 'maxResults', { max: 250 }),
    ]
  }

  getOrder() {
    return 34
  }
}
