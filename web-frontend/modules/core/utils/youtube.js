// The `nocookie` domain doesn't set any tracking cookies until the visitor actually
// starts playing a video.
const PLAYER_HOST = 'https://www.youtube-nocookie.com'
const IFRAME_API_URL = 'https://www.youtube.com/iframe_api'

let iframeApiPromise = null

/**
 * The `mqdefault` thumbnail is used because it's the largest one that YouTube
 * guarantees to exist for every video.
 */
export function getYouTubeThumbnailUrl(videoId) {
  return `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`
}

/**
 * Lazily loads the YouTube iframe player API and resolves with the global `YT` object.
 * The script is only requested once, no matter how many players are created. Rejects if
 * the script can't be loaded, which is the case in an installation without internet
 * access.
 */
export function loadYouTubeIframeApi() {
  if (iframeApiPromise === null) {
    iframeApiPromise = new Promise((resolve, reject) => {
      if (window.YT?.Player) {
        return resolve(window.YT)
      }

      // The API calls this global function when it's done loading. Another script could
      // already have registered one, so it must be kept intact.
      const existing = window.onYouTubeIframeAPIReady
      window.onYouTubeIframeAPIReady = () => {
        existing?.()
        resolve(window.YT)
      }

      const script = document.createElement('script')
      script.src = IFRAME_API_URL
      script.onerror = () => {
        iframeApiPromise = null
        reject(new Error('Could not load the YouTube iframe API.'))
      }
      document.head.appendChild(script)
    })
  }
  return iframeApiPromise
}

/**
 * Creates a player that immediately starts playing and calls `onEnded` when the video
 * has finished.
 */
export async function createYouTubePlayer(element, videoId, onEnded) {
  const YT = await loadYouTubeIframeApi()
  return new YT.Player(element, {
    host: PLAYER_HOST,
    videoId,
    playerVars: { autoplay: 1, rel: 0, modestbranding: 1 },
    events: {
      onReady: (event) => event.target.playVideo(),
      onStateChange: (event) => {
        if (event.data === YT.PlayerState.ENDED) {
          onEnded()
        }
      },
    },
  })
}
