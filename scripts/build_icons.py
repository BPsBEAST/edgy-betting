#!/usr/bin/env python3
"""Rasterize the SAME repository SVG logo for iPhone/Android install icons."""
from pathlib import Path
import cairosvg

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"site"/"assets"
OUT.mkdir(parents=True,exist_ok=True)
logo=(ROOT/"assets"/"edgy-mark.svg").read_bytes()
for size in (180,192,512):
    target=OUT/f"edgy-icon-{size}.png"
    cairosvg.svg2png(bytestring=logo,write_to=str(target),
      output_width=size,output_height=size,background_color="#090d16")
    print("Generated",target)
