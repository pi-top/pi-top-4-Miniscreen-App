from enum import Enum, auto

import PIL.ImageDraw
from pitop.miniscreen.oled.assistant import MiniscreenAssistant

from ...viewport import ViewportManager
from .connection import Page as ConnectionPage


class Page(Enum):
    CONNECTION = auto()


class PageFactory:
    pages = {
        Page.CONNECTION: ConnectionPage,
    }

    @staticmethod
    def get_page(page_type: Page):
        return PageFactory.pages[page_type]


class Viewport(ViewportManager):
    def __init__(self, miniscreen, page_redraw_speed):
        def overlay(miniscreen, image):
            title_overlay_h = 19

            # Empty the top of the image
            PIL.ImageDraw.Draw(image).rectangle(
                ((0, 0), (miniscreen.size[0], title_overlay_h)), fill=1
            )

            # 1px overlay separator
            PIL.ImageDraw.Draw(image).rectangle(
                ((0, title_overlay_h), (miniscreen.size[0], title_overlay_h)), fill=0
            )

            asst = MiniscreenAssistant(miniscreen.mode, miniscreen.size)
            asst.render_text(
                image,
                xy=(miniscreen.size[0] / 2, miniscreen.size[1] / 6),
                text="M E N U",
                wrap=False,
                font=asst.get_mono_font_path(bold=True),
                fill=0,
            )

        super().__init__(
            miniscreen,
            PageFactory,
            Page,
            page_redraw_speed,
            overlay_render_func=overlay,
        )