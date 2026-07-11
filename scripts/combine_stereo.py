"""Kombiniert zwei Equirectangular-Panoramen (linkes/rechtes Auge)
zu einem Top-Bottom-Stereo-Panorama (links oben, rechts unten).

Verwendung:
    python combine_stereo.py <links.jpg> <rechts.jpg> <ausgabe.jpg> [--yaw-offset GRAD]

  --yaw-offset  dreht das rechte Panorama horizontal (Grad), falls die beiden
                Stitches nicht auf denselben Yaw-Nullpunkt ausgerichtet sind.
"""
import sys

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # grosse Panoramen erlauben


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 3:
        print(__doc__)
        sys.exit(1)
    left_path, right_path, out_path = args

    yaw = 0.0
    for i, a in enumerate(sys.argv):
        if a == "--yaw-offset" and i + 1 < len(sys.argv):
            yaw = float(sys.argv[i + 1])

    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")

    # auf gemeinsame Groesse bringen (kleinere Breite gewinnt)
    w = min(left.width, right.width)
    h = w // 2  # equirectangular ist 2:1
    if (left.width, left.height) != (w, h):
        left = left.resize((w, h), Image.LANCZOS)
    if (right.width, right.height) != (w, h):
        right = right.resize((w, h), Image.LANCZOS)

    if yaw != 0.0:
        shift = int(round(yaw / 360.0 * w)) % w
        if shift:
            r = right
            right = Image.new("RGB", (w, h))
            right.paste(r.crop((shift, 0, w, h)), (0, 0))
            right.paste(r.crop((0, 0, shift, h)), (w - shift, 0))

    combo = Image.new("RGB", (w, h * 2))
    combo.paste(left, (0, 0))
    combo.paste(right, (0, h))
    combo.save(out_path, quality=92)
    print(f"Stereo-Panorama (Top-Bottom, {w}x{h * 2}) -> {out_path}")


if __name__ == "__main__":
    main()
