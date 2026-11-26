import { redactPrivateLinks } from '@baserow/modules/core/utils/templatePrivateLink'

/**
 * The visitors of a published application are not Baserow users, and its owner
 * can't ask them for consent on our behalf. On a published application, analytics
 * and monitoring therefore store nothing in the browser, and only anonymous page
 * views are collected.
 */

/**
 * Whether the hostname serves Baserow itself, as opposed to a published
 * application or the preview of the editor.
 *
 * @param {string} hostname The hostname of the current page.
 * @param {object} publicConfig The public runtime config.
 */
export const isWebFrontendHostname = (
  hostname,
  { publicWebFrontendUrl, extraPublicWebFrontendHostnames }
) =>
  new URL(publicWebFrontendUrl).hostname === hostname ||
  (extraPublicWebFrontendHostnames || []).includes(hostname)

/**
 * Whether the hostname serves the preview of the editor.
 *
 * @param {string} hostname The hostname of the current page.
 * @param {object} publicConfig The public runtime config.
 */
export const isBuilderPreviewHostname = (hostname, { builderPreviewUrl }) =>
  !!builderPreviewUrl && new URL(builderPreviewUrl).hostname === hostname

/**
 * Whether the hostname serves a published application, as opposed to Baserow
 * itself or the preview of the editor, which only Baserow users can open.
 *
 * @param {string} hostname The hostname of the current page.
 * @param {object} publicConfig The public runtime config.
 */
export const isPublishedSite = (hostname, publicConfig) =>
  !isWebFrontendHostname(hostname, publicConfig) &&
  !isBuilderPreviewHostname(hostname, publicConfig)

/**
 * The placeholder that PostHog replaces with the anonymous visitor of the day.
 */
const COOKIELESS_DISTINCT_ID = '$posthog_cookieless'

/**
 * The only properties of a page view that leave a published application.
 * `$raw_user_agent` and `$host` are needed by PostHog to count the daily visitors
 * without a cookie, and it doesn't store the user agent. `$process_person_profile`
 * is false, which tells PostHog not to create a person for the visitor.
 */
const PUBLISHED_SITE_PAGE_VIEW_PROPERTIES = new Set([
  'token',
  '$cookieless_mode',
  '$cookieless_extra',
  '$process_person_profile',
  '$raw_user_agent',
  '$host',
  '$current_url',
  '$pathname',
  '$referring_domain',
  '$browser',
  '$os',
  '$device_type',
  '$lib',
  '$lib_version',
  '$insert_id',
  '$time',
])

/**
 * A PostHog `before_send` hook that drops every event of a published application
 * but the page views, and every property of a page view that isn't needed for
 * anonymous statistics.
 */
export const publishedSiteBeforeSend = (event) => {
  if (event?.event !== '$pageview') {
    return null
  }
  return {
    uuid: event.uuid,
    event: event.event,
    timestamp: event.timestamp,
    properties: {
      ...Object.fromEntries(
        Object.entries(event.properties || {}).filter(([name]) =>
          PUBLISHED_SITE_PAGE_VIEW_PROPERTIES.has(name)
        )
      ),
      // PostHog replaces this value with the anonymous visitor of the day. It's
      // forced because PostHog reads the identifier that a visit before this
      // change stored in the browser, before removing it.
      distinct_id: COOKIELESS_DISTINCT_ID,
    },
  }
}

/**
 * The properties of the page view of a published application. The URL is the
 * path of the page as defined in the editor, like `/event/:id`, because the real
 * one and its query string can identify the visitor. The hostname makes the
 * anonymous daily visitor differ between two applications of the same domain.
 *
 * @param {object} location The `window.location` of the page.
 * @param {object} page The page that is visited.
 */
export const getPublishedPageViewProperties = ({ origin, hostname }, page) => ({
  $current_url: `${origin}${page.path}`,
  $pathname: page.path,
  $cookieless_extra: hostname,
})

/**
 * The options PostHog is initialized with.
 *
 * @param {object} options
 * @param {string} options.host The host of PostHog.
 * @param {boolean} options.publishedSite Whether the page is a published
 *   application.
 */
export const getPosthogOptions = ({ host, publishedSite }) => {
  if (!publishedSite) {
    return {
      api_host: host,
      capture_pageview: false,
      capture_pageleave: false,
      disable_session_recording: true,
      autocapture: {
        css_selector_allowlist: ['[ph-autocapture]'],
      },
      before_send: redactPrivateLinks,
    }
  }
  return {
    api_host: host,
    // Stores nothing in the browser. PostHog counts the visitors of a day with a
    // hash that it can't reverse, which must be enabled in the PostHog project.
    cookieless_mode: 'always',
    person_profiles: 'never',
    capture_pageview: false,
    capture_pageleave: false,
    autocapture: false,
    disable_session_recording: true,
    disable_surveys: true,
    disable_product_tours: true,
    advanced_disable_flags: true,
    // PostHog reads what a visit before this change stored in the browser before
    // removing it, which can still tell it to load one of its optional scripts.
    disable_external_dependency_loading: true,
    // These can be enabled in the PostHog project, which only an explicit value
    // overrides.
    capture_heatmaps: false,
    capture_dead_clicks: false,
    capture_exceptions: false,
    capture_performance: false,
    before_send: publishedSiteBeforeSend,
  }
}

/**
 * The options of the session replay of Sentry. On a published application, the
 * session isn't kept in the session storage, so a replay ends with the page.
 *
 * @param {object} options
 * @param {boolean} options.publishedSite Whether the page is a published
 *   application.
 */
export const getReplayOptions = ({ publishedSite }) => ({
  maskAllText: true,
  blockAllMedia: true,
  ...(publishedSite ? { stickySession: false } : {}),
})
