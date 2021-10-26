import logging

from PIL import Image

from .config import ConfigFactory
from .config.classes.menu_edge_behaviour import MenuEdgeBehaviour
from .viewport import Viewport

logger = logging.getLogger(__name__)


class Menu:
    SCROLL_PX_RESOLUTION = 2

    def __init__(self, size, mode, redraw_speed, config):
        self.mode = mode
        self.size = size
        self.page_index = 0

        self.parent_goes_to_first_page = config.parent_goes_to_first_page
        self.top_edge = config.top_edge
        self.bottom_edge = config.bottom_edge
        self.title_bar = config.title_bar

        window_height = size[1] - self.title_bar.height
        window_size = (size[0], window_height)
        display_size = (size[0], window_height * len(config.children))

        config_factory = ConfigFactory(window_size, mode, redraw_speed)

        self.pages = list()
        for page_name, page_config in config.children.items():
            self.pages.append(config_factory.get(page_config))

        self.viewport = Viewport(
            window_size=window_size,
            display_size=display_size,
            mode=mode,
        )

        for i, page in enumerate(self.pages):
            for upperleft_xy, hotspots in page.hotspots.items():
                for hotspot in hotspots:
                    # Adjust page's xy to match position in viewport
                    pos = (
                        upperleft_xy[0],
                        upperleft_xy[1] + i * window_height,
                    )
                    self.viewport.add_hotspot(hotspot, pos, collection_id=page)

    @property
    def current_page(self):
        return self.pages[self.page_index]

    @property
    def y_pos(self):
        return self.viewport._position[1]

    @y_pos.setter
    def y_pos(self, pos):
        return self.viewport.set_position((0, pos))

    def move_to_page(self, index):
        self.page_index = index
        self.y_pos = self.page_index * self.viewport.height

    @property
    def image(self):
        im = Image.new(self.mode, self.size)
        im.paste(self.title_bar, (0, 0) + (self.size[1], self.title_bar.height - 1))
        im.paste(self.viewport.image, (0, self.title_bar.height) + self.size)

        return im

    def set_page_index_to(self, page_index):
        self.page_index = page_index

    def set_page_to_previous(self):
        if self.needs_to_scroll:
            return

        previous_index = self.page_index
        self.set_page_index_to(self.get_previous_page_index())
        logger.debug(f"Page index: {previous_index} -> {self.page_index}")

    def set_page_to_next(self):
        if self.needs_to_scroll:
            return

        previous_index = self.page_index
        self.set_page_index_to(self.get_next_page_index())
        logger.debug(f"Page index: {previous_index} -> {self.page_index}")

    def get_previous_page_index(self):
        if self.page_index == 0:
            if self.top_edge == MenuEdgeBehaviour.NONE:
                return self.page_index

            elif self.top_edge == MenuEdgeBehaviour.BOUNCE:
                return self.get_next_page_index()

            elif self.top_edge == MenuEdgeBehaviour.LOOP:
                return len(self.pages) - 1

        return self.page_index - 1

    def get_next_page_index(self):
        if self.page_index == len(self.pages) - 1:
            if self.bottom_edge == MenuEdgeBehaviour.NONE:
                return self.page_index

            elif self.bottom_edge == MenuEdgeBehaviour.BOUNCE:
                return self.get_previous_page_index()

            elif self.bottom_edge == MenuEdgeBehaviour.LOOP:
                return 0

        return self.page_index + 1

    @property
    def needs_to_scroll(self):
        correct_y_pos = self.page_index * self.current_page.height
        return self.y_pos != correct_y_pos

    def update_scroll_position(self):
        if not self.needs_to_scroll:
            return

        correct_y_pos = self.page_index * self.viewport.window_height
        move_down = correct_y_pos > self.y_pos
        self.y_pos += self.SCROLL_PX_RESOLUTION * (1 if move_down else -1)