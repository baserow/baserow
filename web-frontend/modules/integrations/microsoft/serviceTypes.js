import {
  ExternalServiceType,
  formulaField,
  integerField,
} from '@baserow/modules/integrations/common/externalServiceType'
import { MicrosoftIntegrationType } from '@baserow/modules/integrations/microsoft/integrationTypes'

class MicrosoftServiceType extends ExternalServiceType {
  static get integrationTypeClass() {
    return MicrosoftIntegrationType
  }
}

const outlookCalendarField = formulaField('calendar_id', 'outlookCalendarId', {
  help: 'outlookCalendarIdHelp',
})

const eventFields = (required) => [
  formulaField('subject', 'eventTitle', { required }),
  formulaField('body', 'eventDescription'),
  formulaField('location', 'eventLocation'),
  formulaField('start', 'eventStart', { required, help: 'eventTimeHelp' }),
  formulaField('end', 'eventEnd', { required, help: 'eventTimeHelp' }),
  formulaField('time_zone', 'eventTimeZone', {
    placeholder: 'eventTimeZonePlaceholder',
    help: 'outlookTimeZoneHelp',
  }),
  formulaField('attendees', 'eventAttendees', {
    placeholder: 'emailsPlaceholder',
  }),
]

export class MicrosoftTeamsSendMessageServiceType extends MicrosoftServiceType {
  static getType() {
    return 'microsoft_teams_send_message'
  }

  static get i18nKey() {
    return 'microsoftTeamsSendMessage'
  }

  get icon() {
    return 'iconoir-chat-bubble'
  }

  get formFields() {
    return [
      formulaField('team_id', 'teamId', { required: true, help: 'teamIdHelp' }),
      formulaField('channel_id', 'channelId', {
        required: true,
        help: 'channelIdHelp',
      }),
      formulaField('message', 'message', { required: true }),
    ]
  }

  getOrder() {
    return 40
  }
}

export class OutlookSendEmailServiceType extends MicrosoftServiceType {
  static getType() {
    return 'outlook_send_email'
  }

  static get i18nKey() {
    return 'outlookSendEmail'
  }

  get icon() {
    return 'iconoir-send-mail'
  }

  get formFields() {
    return [
      formulaField('to_emails', 'toEmails', {
        required: true,
        placeholder: 'emailsPlaceholder',
        help: 'emailsHelp',
      }),
      formulaField('cc_emails', 'ccEmails', {
        placeholder: 'emailsPlaceholder',
      }),
      formulaField('bcc_emails', 'bccEmails', {
        placeholder: 'emailsPlaceholder',
      }),
      formulaField('subject', 'subject', { required: true }),
      formulaField('body', 'body', {
        required: true,
        help: 'plainTextBodyHelp',
      }),
    ]
  }

  getOrder() {
    return 41
  }
}

export class OutlookCalendarCreateEventServiceType extends MicrosoftServiceType {
  static getType() {
    return 'outlook_calendar_create_event'
  }

  static get i18nKey() {
    return 'outlookCalendarCreateEvent'
  }

  get icon() {
    return 'iconoir-calendar-plus'
  }

  get formFields() {
    return [outlookCalendarField, ...eventFields(true)]
  }

  getOrder() {
    return 42
  }
}

export class OutlookCalendarUpdateEventServiceType extends MicrosoftServiceType {
  static getType() {
    return 'outlook_calendar_update_event'
  }

  static get i18nKey() {
    return 'outlookCalendarUpdateEvent'
  }

  get icon() {
    return 'iconoir-edit-pencil'
  }

  get formFields() {
    return [
      outlookCalendarField,
      formulaField('event_id', 'eventId', {
        required: true,
        help: 'eventIdHelp',
      }),
      ...eventFields(false),
    ]
  }

  getOrder() {
    return 43
  }
}

export class OutlookCalendarDeleteEventServiceType extends MicrosoftServiceType {
  static getType() {
    return 'outlook_calendar_delete_event'
  }

  static get i18nKey() {
    return 'outlookCalendarDeleteEvent'
  }

  get icon() {
    return 'iconoir-calendar-minus'
  }

  get formFields() {
    return [
      outlookCalendarField,
      formulaField('event_id', 'eventId', {
        required: true,
        help: 'eventIdHelp',
      }),
    ]
  }

  getOrder() {
    return 44
  }
}

export class OutlookCalendarListEventsServiceType extends MicrosoftServiceType {
  static getType() {
    return 'outlook_calendar_list_events'
  }

  static get i18nKey() {
    return 'outlookCalendarListEvents'
  }

  get icon() {
    return 'iconoir-calendar'
  }

  get formFields() {
    return [
      outlookCalendarField,
      formulaField('start', 'eventsFrom', { help: 'outlookWindowHelp' }),
      formulaField('end', 'eventsUntil', { help: 'outlookWindowHelp' }),
      integerField('max_results', 'maxResults', { max: 250 }),
    ]
  }

  getOrder() {
    return 45
  }
}
