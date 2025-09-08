#!/usr/bin/env python3
# scripts/optimize_images.py

import logging
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps

# Add project root to sys.path for imports
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from app.services.metrics import METRICS

log = logging.getLogger("optimize_images")


class ImageOptimizer:
    """Optimizes images by resizing and converting to WebP (alpha preserved when present)."""

    def __init__(self, input_dirs, output_dir, quality=80, max_size=(1920, 1920)):
        self.input_dirs = [Path(d) for d in input_dirs]
        self.output_dir = Path(output_dir)
        self.quality = int(quality)
        self.max_size = tuple(max_size)
        self.supported_formats = {".jpg", ".jpeg", ".png", ".webp"}

    def optimize(self):
        """Process images in input directories, converting to WebP and compressing.

        Returns:
            Tuple of (processed_count, error_count).
        """
        processed, errors = 0, 0
        self.output_dir.mkdir(parents=True, exist_ok=True)

        seen_outputs = set()
        for input_dir in self.input_dirs:
            if not input_dir.is_dir():
                log.warning("Input directory not found: %s", input_dir)
                errors += 1
                METRICS.increment("images.input_missing")
                continue

            for filepath in input_dir.rglob("*"):
                if filepath.suffix.lower() not in self.supported_formats:
                    continue

                # Compute a stable relative name to avoid collisions across dirs
                rel = filepath.relative_to(input_dir)
                rel_name = "-".join(rel.parts[:-1] + (rel.stem + ".webp",)) if rel.parts else filepath.stem + ".webp"
                out_path = self.output_dir / rel_name

                if rel_name in seen_outputs:
                    log.info("Skipping duplicate output name: %s", rel_name)
                    continue
                seen_outputs.add(rel_name)

                ok = self._optimize_image(filepath, out_path)
                if ok:
                    processed += 1
                    METRICS.increment("images.optimized_ok")
                else:
                    errors += 1
                    METRICS.increment("images.optimized_error")

        log.info("Optimization complete: %d processed, %d errors", processed, errors)
        return processed, errors

    def _optimize_image(self, input_path, output_path):
        """Optimize a single image by resizing and converting to WebP."""
        try:
            with Image.open(input_path) as img:
                # Normalize orientation via EXIF
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass

                # Resize if larger than max_size (thumbnail preserves aspect)
                img.thumbnail(self.max_size, Image.Resampling.LANCZOS)

                # Determine save params; preserve alpha if present
                save_params = {
                    "format": "WEBP",
                    "quality": self.quality,
                    "optimize": True,
                    "method": 6,  # better compression
                }

                if img.mode in ("RGBA", "LA"):
                    # Keep alpha; Pillow handles alpha for WebP
                    pass
                elif img.mode == "P":
                    img = img.convert("RGBA")  # palette -> RGBA to keep transparency if any
                else:
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")

                output_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(output_path, **save_params)
                log.info("Optimized %s -> %s", input_path, output_path)
                return True
        except Exception as e:
            log.error("Error optimizing %s: %s", input_path, e)
            return False


def _default_paths():
    try:
        from app.config import Config
        cfg = Config()
        input_dirs = [cfg.PLAYME_DIR, cfg.STATIC_IMG_DIR]
        output_dir = cfg.OPTIMIZED_IMG_DIR or REPO / "data" / "optimized"
        return input_dirs, output_dir
    except Exception:
        return [
            REPO / "data" / "playme",
            REPO / "app" / "static" / "img",
        ], REPO / "data" / "optimized"


def main():
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    input_dirs, output_dir = _default_paths()
    optimizer = ImageOptimizer(input_dirs, output_dir)
    processed, errors = optimizer.optimize()
    print("Optimization complete: %d images processed, %d errors" % (processed, errors))
    sys.exit(0 if errors == 0 else 1)


if __name__ == "__main__":
    main()
