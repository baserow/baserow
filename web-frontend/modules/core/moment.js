// Moment should always be imported from here. This will enforce that the timezone
// is always included. There were some problems when Baserow is installed as a
// dependency and then moment-timezone does not work. Still will resolve that issue.
import moment from 'moment-timezone'
import 'moment/dist/locale/fr'
import 'moment/dist/locale/nl'
import 'moment/dist/locale/de'
import 'moment/dist/locale/es'
import 'moment/dist/locale/it'
import 'moment/dist/locale/pl'
import 'moment/dist/locale/ko'
import 'moment/dist/locale/uk'

export default moment
