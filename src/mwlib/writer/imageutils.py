#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.rst for additional licensing information.


from PIL import Image


class ImageUtils:
    def __init__(
        self,
        print_width,
        print_height,
        default_thumb_width,
        img_min_res,
        img_max_thumb_width,
        img_max_thumb_height,
        img_inline_scale_factor,
        print_width_px,
    ):
        self.print_width = print_width
        self.print_height = print_height
        self.default_thumb_width = default_thumb_width
        self.img_min_res = img_min_res
        self.img_max_thumb_width = img_max_thumb_width
        self.img_max_thumb_height = img_max_thumb_height
        self.img_inline_scale_factor = img_inline_scale_factor
        self.print_width_px = print_width_px

    def get_image_size(
        self,
        img_node,
        img_path=None,
        max_print_width=None,
        max_print_height=None,
        full_size_thumbs=False,
        img_size=None,
    ):
        max_width = getattr(img_node, "width", None)
        max_height = getattr(img_node, "height", None)
        if img_path:
            try:
                img = Image.open(img_path)
            except OSError:  # img either missing or corrupt
                return 0, 0
            px_width, px_height = img.size
        else:
            px_width, px_height = img_size

        aspect_ratio, max_width = self._compute_aspect_ratio_and_max_width(
            max_height, max_width, px_height, px_width
        )

        # check if img_node is thumb, then assign default width
        max_width = self._compute_max_width_for_thumbs(
            full_size_thumbs, img_node, max_width
        )

        if not max_width:
            max_width = min(self.print_width_px, px_width)
        max_width = min(self.print_width_px, max_width)
        scale = max_width / self.print_width_px
        img_print_width = self.print_width * scale

        if max_print_width and img_print_width > max_print_width:
            img_print_width = max_print_width

        if max_print_height:
            img_print_width = min(img_print_width, max_print_height * aspect_ratio)

        # check min resolution
        resulting_dpi = px_width / img_print_width * 72
        if resulting_dpi < self.img_min_res:
            img_print_width = (resulting_dpi / self.img_min_res) * img_print_width

        # check size limits for floating images
        if getattr(img_node, "floating", False):
            img_print_width = min(
                img_print_width,
                self.print_width * self.img_max_thumb_width,
                self.print_height * self.img_max_thumb_height * aspect_ratio,
            )

        if img_node.is_inline():
            if img_print_width < self.print_width / 2:  # scale "small" inline images
                img_print_width *= self.img_inline_scale_factor
            else:  # FIXME: full width images are 12pt too wide - we need to check why
                img_print_width -= 12

        img_print_width = min(
            img_print_width, self.print_width, self.print_height * aspect_ratio * 0.9
        )
        img_print_height = img_print_width / aspect_ratio
        return img_print_width, img_print_height

    @staticmethod
    def _compute_aspect_ratio_and_max_width(max_height, max_width,
                                            px_height, px_width):
        aspect_ratio = px_width / px_height
        if max_height and max_width:
            if max_height * aspect_ratio > max_width:
                max_height = max_width / aspect_ratio
            elif max_width / aspect_ratio > max_height:
                max_width = max_height * aspect_ratio
        if max_height and not max_width:
            max_width = max_height * aspect_ratio
        return aspect_ratio, max_width

    def _compute_max_width_for_thumbs(self, full_size_thumbs,
                                      img_node, max_width):
        if (
            getattr(img_node, "thumb", None)
            or getattr(img_node, "frame", None)
            or getattr(img_node, "frameless", None)
            or getattr(img_node, "align", None) in ["right", "left"]
        ):
            max_width = max_width or self.default_thumb_width
            if full_size_thumbs:
                max_width = self.print_width_px
            if getattr(img_node, "align", None) not in ["center", "none"]:
                img_node.floating = True
            if getattr(img_node, "upright", 1):
                max_width *= getattr(img_node, "upright", 1)
        return max_width
