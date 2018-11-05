#!/usr/bin/env python

from hotspot.common import title_text


def page(title="Title"):
    def render(draw, width, height):
        margin = 3
        title_text(draw, margin, width, text=title)

    return render
