// `replay_events` cursor sentinels. Must match the constants in
// backend/src/baserow/ws/realtime_events.py.
//
// FIRST_CONNECT_CURSOR: first connect of a session, ask for a baseline only.
// NO_REPLAY_AVAILABLE:  reconnect with no usable high-water mark, force refresh.
export const FIRST_CONNECT_CURSOR = -1
export const NO_REPLAY_AVAILABLE = -2
