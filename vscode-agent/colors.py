"""Compute VS Code title bar colors for an agent worktree.

Usage: python3 colors.py <slug>
Output: shell eval-able variable assignments (tbarbg, tbarfg, tbaribg)
"""

import colorsys
import hashlib
import sys

slug = sys.argv[1]
h = int(hashlib.md5(slug.encode()).hexdigest()[:8], 16) % 360

r, g, b = colorsys.hls_to_rgb(h / 360, 0.14, 0.45)
bg = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

r2, g2, b2 = colorsys.hls_to_rgb(h / 360, 0.11, 0.35)
ibg = f"#{int(r2 * 255):02x}{int(g2 * 255):02x}{int(b2 * 255):02x}"

print(f"tbarbg={bg}")
print(f"tbarfg=#cccccc")
print(f"tbaribg={ibg}")
