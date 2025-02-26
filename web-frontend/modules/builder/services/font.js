const url = "https://api.fontsource.org/v1/fonts?type=google"

export default (client) => {
  return {
    fetchFonts() {
      return client.get(url)
    },
  }
}
