// Keep container health checks outside the Vue renderer so probing readiness
// never triggers compilation of the application page graph.
export default defineEventHandler(() => 'OK')
