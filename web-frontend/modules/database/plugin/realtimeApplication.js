import { registerRealtimeEvents } from '@baserow/modules/database/realtime'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  registerRealtimeEvents(nuxtApp.$realtime)
}
