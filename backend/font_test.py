
import requests

# resp len 1927
# in bytes: 490965
# url = "https://api.fontsource.org/v1/fonts"

# resp len 1809
# in bytes: 461842
url = "https://api.fontsource.org/v1/fonts?type=google"
resp = requests.get(url)
breakpoint()