import logging

from pitop.battery import Battery

from ...hotspots.image_hotspot import Hotspot as ImageHotspot
from ...hotspots.rectangle_hotspot import Hotspot as RectangleHotspot
from ...hotspots.text_hotspot import Hotspot as TextHotspot
from ...utils import get_image_file_path
from ..base import Page as PageBase

logger = logging.getLogger(__name__)

FONT_SIZE = 19
ICON_HEIGHT = 22
RECTANGLE_HOTSPOT_SIZE = (37, 14)
BATTERY_LEFT_MARGIN = 15
CAPACITY_RECTANGLE_LEFT_OFFSET = 4
CAPACITY_RECTANGLE_LEFT_MARGIN = BATTERY_LEFT_MARGIN + CAPACITY_RECTANGLE_LEFT_OFFSET


class Page(PageBase):
    def __init__(self, interval, size, mode, config):
        super().__init__(interval, size, mode, config)

        self.battery = Battery()
        self.cable_connected = self.battery.is_charging or self.battery.is_full
        self.capacity = 0
        try:
            self.capacity = self.battery.capacity
        except Exception:
            pass

        self.setup_hotspots()

    def setup_hotspots(self):
        self.text_hotspot = TextHotspot(
            interval=self.interval,
            mode=self.mode,
            size=(self.short_section_width, self.height),
            text=f"{self.capacity}%",
            font_size=FONT_SIZE,
            anchor="lt",
            xy=(0, 0),
        )

        self.battery_base_hotspot = ImageHotspot(
            interval=self.interval,
            mode=self.mode,
            size=(self.short_section_width, ICON_HEIGHT),
            image_path=None,
        )

        self.rectangle_hotspot = RectangleHotspot(
            interval=self.interval,
            mode=self.mode,
            size=RECTANGLE_HOTSPOT_SIZE,
            bounding_box=(0, 0, 0, 0),
        )

        text_hotspot_pos = (
            self.long_section_width,
            self.vertical_middle_position(self.text_hotspot.text_size[1]),
        )
        battery_hotspot_pos = (
            BATTERY_LEFT_MARGIN,
            self.vertical_middle_position(ICON_HEIGHT),
        )
        rectangle_hotspot_pos = (
            CAPACITY_RECTANGLE_LEFT_MARGIN,
            self.vertical_middle_position(RECTANGLE_HOTSPOT_SIZE[1]),
        )

        self.hotspots = {
            battery_hotspot_pos: [self.battery_base_hotspot],
            rectangle_hotspot_pos: [self.rectangle_hotspot],
            text_hotspot_pos: [self.text_hotspot],
        }

        self.update_hotspots_properties()
        self.setup_events()

    def update_hotspots_properties(self):
        text = "Unknown"
        if self.capacity is not None:
            text = f"{self.capacity}%"
        self.text_hotspot.text = text

        image_path = get_image_file_path("sys_info/battery_shell_empty.png")
        if self.cable_connected:
            image_path = get_image_file_path("sys_info/battery_shell_charging.png")
        self.battery_base_hotspot.image_path = image_path

        bounding_box = (0, 0, 0, 0)
        if not self.cable_connected:
            bar_width = int(self.rectangle_hotspot.size[0] * self.capacity / 100)
            bounding_box = (0, 0, bar_width, self.rectangle_hotspot.size[1])
        self.rectangle_hotspot.bounding_box = bounding_box

    def setup_events(self):
        def update_capacity(capacity):
            self.capacity = capacity
            self.update_hotspots_properties()

        def update_charging_state(state):
            self.cable_connected = state in ("charging", "full")
            self.update_hotspots_properties()

        self.battery.on_capacity_change = update_capacity
        self.battery.when_charging = lambda: update_charging_state("charging")
        self.battery.when_full = lambda: update_charging_state("full")
        self.battery.when_discharging = lambda: update_charging_state("discharging")
