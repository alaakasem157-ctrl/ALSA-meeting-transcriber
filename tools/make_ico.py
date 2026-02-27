from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "assets" / "logo-ALSA.png"
dst = ROOT / "assets" / "app.ico"

if not src.exists():
    raise SystemExit(f"Missing: {src}")

img = Image.open(src).convert("RGBA")

sizes = [256]
icons = [img.resize((s, s), Image.LANCZOS) for s in sizes]

dst.parent.mkdir(parents=True, exist_ok=True)
icons[0].save(dst, format="ICO", sizes=[(s, s) for s in sizes])

print("Wrote:", dst)