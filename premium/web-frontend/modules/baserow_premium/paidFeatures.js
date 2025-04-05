import { Registerable } from '@baserow/modules/core/registry'

export class PaidFeature extends Registerable {
  getPlan() {
    throw new Error('@TODO')
  }

  getName() {
    throw new Error('@TODO')
  }

  getIconClass() {
    throw new Error('@TODO')
  }

  getImage() {
    return null
  }

  getContent() {
    throw new Error('@TODO')
  }

  getOrder() {
    return 100
  }
}

export class FormSurveyModePaidFeature extends PaidFeature {
  static getType() {
    return 'form_survey_mode'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-reports'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.surveyForm')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class RowCommentsPaidFeature extends PaidFeature {
  static getType() {
    return 'row_comments'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-multi-bubble'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.rowComments')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class RowNotificationsPaidFeature extends PaidFeature {
  static getType() {
    return 'row_notifications'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-bell'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.rowNotifications')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class KanbanViewPaidFeature extends PaidFeature {
  static getType() {
    return 'kanban_view'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'baserow-icon-kanban'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.kanbanView')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class CalendarViewPaidFeature extends PaidFeature {
  static getType() {
    return 'calendar_view'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'baserow-icon-calendar'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.calendarView')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class TimelineViewPaidFeature extends PaidFeature {
  static getType() {
    return 'timeline_view'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'baserow-icon-timeline'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.timelineView')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class PersonalViewsPaidFeature extends PaidFeature {
  static getType() {
    return 'personal_views'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-lock'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.personalViews')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class ExportsPaidFeature extends PaidFeature {
  static getType() {
    return 'exports'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-database-export'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.exports')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class RowColoringPaidFeature extends PaidFeature {
  static getType() {
    return 'row_coloring'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-palette'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.rowColoring')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class PublicLogoRemovalPaidFeature extends PaidFeature {
  static getType() {
    return 'public_logo_removal'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-eye-close'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.publicLogoRemoval')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class AIPaidFeature extends PaidFeature {
  static getType() {
    return 'ai_features'
  }

  getPlan() {
    return 'Premium'
  }

  getIconClass() {
    return 'iconoir-magic-wand'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.aiFeatures')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class ChartPaidFeature extends PaidFeature {
  static getType() {
    return 'chart'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'baserow-icon-dashboard'
  }

  getName() {
    return this.app.i18n.t('premiumFeatures.chartWidget')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}
