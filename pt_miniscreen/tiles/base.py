import logging
import time
from threading import Thread
from time import sleep
from typing import Dict, List

from PIL import Image
from pitop.miniscreen.oled.assistant import MiniscreenAssistant

from ..event import AppEvents, post_event, subscribe
from ..hotspots.base import HotspotInstance

logger = logging.getLogger(__name__)


class Tile:
    def __init__(self, size, pos=(0, 0)) -> None:
        self._size = size
        self._pos = pos
        self.cached_images: Dict = dict()
        self.image_caching_threads: Dict = dict()
        self.update_cached_images = False
        self.active = False
        self.hotspot_instances: List[HotspotInstance] = list()
        self._render_size = self.size

        self.subscribe_to_button_events()

    @property
    def window_position(self):
        return (0, 0)

    @property
    def size(self):
        if callable(self._size):
            return self._size()

        return self._size

    @size.setter
    def size(self, xy):
        self._size = xy

    @property
    def pos(self):
        if callable(self._pos):
            return self._pos()

        return self._pos

    @pos.setter
    def pos(self, xy):
        self._pos = xy

    @property
    def bounding_box(self):
        return (0, 0, self.width - 1, self.height - 1)

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    @height.setter
    def height(self, value):
        self.size = (self.width, value)

    def start(self):
        self.update_cached_images = True
        for _, thread in self.image_caching_threads.items():
            thread.start()

    def stop(self):
        self.update_cached_images = False
        for hotspot, thread in self.image_caching_threads.items():
            thread.join(0)
        logger.debug("stop - stopped all threads")

    def _paste_hotspot_into_image(self, hotspot_instance, image):
        if (
            not hotspot_instance.hotspot.draw_white
            and not hotspot_instance.hotspot.draw_black
        ):
            return

        if not self.update_cached_images:
            logger.debug(
                "paste_hotspot_into_image - Not caching images anymore - returning"
            )
            return

        hotspot_image = self.cached_images.get(hotspot_instance.hotspot)
        if not hotspot_image:
            return

        if hotspot_instance.hotspot.invert:
            hotspot_image = MiniscreenAssistant(
                "1", hotspot_instance.hotspot.size
            ).invert(hotspot_image)

        mask = hotspot_instance.hotspot.mask(hotspot_image)
        pos = hotspot_instance.xy
        # box = pos + (pos[0] + hotspot_image.size[0], pos[1] + hotspot_image.size[1])
        logger.debug(
            f"viewport.paste_hotspot_into_image - hotspot image size: {hotspot_image.size}"
        )
        logger.debug(
            f"viewport.paste_hotspot_into_image - base image size: {image.size}"
        )
        logger.debug(
            f"viewport.paste_hotspot_into_image - hotspot xy: {hotspot_instance.xy}"
        )
        logger.debug(f"viewport.paste_hotspot_into_image - position: {pos}")
        image.paste(hotspot_image, pos, mask)

    def set_hotspot_instances(self, hotspot_instances, start=False):
        self.clear()
        for hotspot_instance in hotspot_instances:
            self.add_hotspot_instance(hotspot_instance)
        if start:
            self.start()

    def add_hotspot_instance(self, hotspot_instance):
        (x, y) = hotspot_instance.xy

        # xy + size = max size needed to render a given hotspot instance
        # self._render_size manages this max size for all added hotspot instances
        max_x = x + hotspot_instance.size[0]
        if max_x > self.render_size[0]:
            self._render_size = (max_x, self.render_size[1])

        max_y = y + hotspot_instance.size[1]
        if max_y > self.render_size[1]:
            self._render_size = (self.render_size[0], max_y)

        logger.debug(f"Tile.add_hotspot_instance {hotspot_instance}")

        if hotspot_instance in self.hotspot_instances:
            raise Exception(f"Hotspot instance {hotspot_instance} already registered")

        self.hotspot_instances.append((hotspot_instance))
        self.cached_images[hotspot_instance.hotspot] = dict()

        self._register_thread(hotspot_instance)

    def remove_hotspot_instance(self, hotspot_instance):
        self.hotspot_instances.remove(hotspot_instance)

    def _register_thread(self, hotspot_instance):
        logger.debug("Caching new image...")
        hotspot = hotspot_instance.hotspot

        def run():
            def cache_new_image():
                self.cached_images[hotspot] = hotspot.image

            logger.debug("Caching new image...")
            cache_new_image()
            logger.debug(
                f"Done caching new image... self.update_cached_images: {self.update_cached_images}"
            )
            while self.update_cached_images:
                # TODO: improve this "busy wait"
                # if not active, there's no need to check - perhaps instead of sleeping,
                # we should wait on an event triggered on active state change?
                #
                # another thing to consider would be to do something similar with 'is overlapping'
                # - if we are not overlapping, and the position is not changing, then this is still
                # busy waiting...
                if self.active and self.is_hotspot_overlapping(hotspot_instance):
                    cache_new_image()
                    post_event(AppEvents.UPDATE_DISPLAYED_IMAGE)
                sleep(hotspot.interval)

        self.image_caching_threads[hotspot] = Thread(
            target=run, args=(), daemon=True, name=hotspot
        )

    def clear(self):
        self.stop()
        self.remove_all_hotspot_instances()

    def remove_all_hotspot_instances(self):
        self.hotspot_instances = list()

    def is_hotspot_overlapping(self, hotspot_instance):
        def calc_bounds(xy, width, height):
            """For width and height attributes, determine the bounding box if
            were positioned at ``(x, y)``."""
            left, top = xy
            right, bottom = left + width, top + height
            return [left, top, right, bottom]

        def range_overlap(a_min, a_max, b_min, b_max):
            """Neither range is completely greater than the other."""
            return (a_min < b_max) and (b_min < a_max)

        l1, t1, r1, b1 = calc_bounds(
            hotspot_instance.xy,
            hotspot_instance.hotspot.width,
            hotspot_instance.hotspot.height,
        )
        l2, t2, r2, b2 = calc_bounds(self.window_position, self.size[0], self.size[1])
        return range_overlap(l1, r1, l2, r2) and range_overlap(t1, b1, t2, b2)

    @property
    def render_size(self):
        return (
            self._render_size
            if self._render_size[0] > self.size[0]
            or self._render_size[1] > self.size[1]
            else self.size
        )

    def get_preprocess_image(self):
        return Image.new("1", self.render_size)

    def process_image(self, image):
        for hotspot_instance in self.hotspot_instances:
            if not self.is_hotspot_overlapping(hotspot_instance):
                continue
            self._paste_hotspot_into_image(hotspot_instance, image)
        return image

    def post_process_image(self, image):
        return image if image.size == self.size else image.crop(box=(0, 0) + self.size)

    @property
    def image(self):
        if not self.update_cached_images:
            logger.debug("Not caching images anymore - returning")
            return

        start = time.time()

        im = self.post_process_image(self.process_image(self.get_preprocess_image()))

        end = time.time()
        logger.debug(f"Time generating image: {end - start}")

        return im

    def handle_select_btn(self):
        return

    def handle_cancel_btn(self):
        return

    def handle_up_btn(self):
        return

    def handle_down_btn(self):
        return

    def subscribe_to_button_events(self):
        subscribe(
            AppEvents.UP_BUTTON_PRESS,
            lambda cb: cb(self.handle_up_btn) if self.active else None,
        )
        subscribe(
            AppEvents.DOWN_BUTTON_PRESS,
            lambda cb: cb(self.handle_down_btn) if self.active else None,
        )
        subscribe(
            AppEvents.SELECT_BUTTON_PRESS,
            lambda cb: cb(self.handle_select_btn) if self.active else None,
        )
        subscribe(
            AppEvents.CANCEL_BUTTON_PRESS,
            lambda cb: cb(self.handle_cancel_btn) if self.active else None,
        )
