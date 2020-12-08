from .Menu import (
    Menu,
    Menus,
)
from .helpers.button_press import ButtonPress

from pitop.miniscreen.buttons import CaseButtons

from pitopcommon.logger import PTLogger
from pitopcommon.pt_os import eula_agreed, is_pi_top_os

from time import sleep
from os import listdir
from re import compile


class MenuManager:
    """Owner class for all Menus. Handles input events and controls menu behaviour."""

    def __init__(self, oled):
        self.__oled = oled

        self.current_menu = None

        self.__buttons = CaseButtons()
        self.__buttons._set_exclusive_mode(False)

        self.__buttons.up.when_pressed = lambda: self.__add_button_press_to_stack(
            ButtonPress(ButtonPress.ButtonType.UP))
        self.__buttons.down.when_pressed = lambda: self.__add_button_press_to_stack(
            ButtonPress(ButtonPress.ButtonType.DOWN))
        self.__buttons.select.when_pressed = lambda: self.__add_button_press_to_stack(
            ButtonPress(ButtonPress.ButtonType.SELECT))
        self.__buttons.cancel.when_pressed = lambda: self.__add_button_press_to_stack(
            ButtonPress(ButtonPress.ButtonType.CANCEL))

        self.__button_press_stack = []
        self.__continue = True
        self.__sleeping = False
        self.__default_frame_sleep_time = 0.1
        self.__frame_sleep_time = self.__default_frame_sleep_time
        self.__current_page_frame_counter = 0
        self.__current_page_frame_counter_limit = 300

        self.__menus = dict()

        # If EULA is not agreed to on pi-topOS, then user is still in onboarding
        # Not the best breadcrumb to look for...
        if is_pi_top_os() and eula_agreed() is False:
            self.__add_menu_to_list(Menus.FIRST_TIME)
            self.change_menu(Menus.FIRST_TIME)
        else:
            self.__add_menu_to_list(Menus.SYS_INFO)
            self.__add_menu_to_list(Menus.MAIN_MENU)
            self.__add_menu_to_list(Menus.PROJECTS)
            self.__add_menu_to_list(Menus.SETTINGS)
            self.change_menu(Menus.SYS_INFO)

    def main_loop(self):
        try:
            while self.__continue:
                # Only attempt to update state if OLED is owned by pt-sys-oled
                if not self.__oled.is_active():
                    self.__update_state()
                    PTLogger.debug(
                        f"Sleep timer: {self.__current_page_frame_counter:.2f} / {self.__current_page_frame_counter_limit}")

                PTLogger.debug("Sleeping for " + str(self.__frame_sleep_time))
                sleep(self.__frame_sleep_time)

                self.__wait_for_oled_control()

        except SystemExit:
            PTLogger.info("Program exited")
            pass

    def stop(self):
        self.__continue = False

    # Public so that hotspots can use this
    def change_menu(self, menu_to_go_to):
        if menu_to_go_to in self.__menus:
            current_menu_name = "<not set>" if self.current_menu is None else self.current_menu.name
            PTLogger.info(
                f"Changing menu from {current_menu_name} to {self.__menus[menu_to_go_to].name}")
            self.current_menu = self.__menus[menu_to_go_to]
            if menu_to_go_to == Menus.PROJECTS:
                self.current_menu.update_pages()
            self.current_menu.refresh(force=True)
            self.__draw_current_menu_page_to_oled()
        else:
            self.stop()
            raise Exception("Unable to find menu: " + str(menu_to_go_to))

    def __add_button_press_to_stack(self, button_press_event):
        if self.__oled.is_active():
            PTLogger.info(
                f"OLED is active - skipping button press: {str(button_press_event.event_type)}")
            return

        if self.__button_locks_exist():
            PTLogger.info(
                f"Buttons locks exist - skipping button press: {str(button_press_event.event_type)}")
            return

        if button_press_event.event_type == ButtonPress.ButtonType.NONE:
            PTLogger.info("NONE button type - skipping button press")
            return

        PTLogger.info(
            "Adding " + str(button_press_event.event_type) + " to stack")
        self.__button_press_stack.append(button_press_event)

    def __sleep_oled(self):
        self.__oled.device.contrast(0)
        # self.__oled.device.hide()
        self.__sleeping = True

    def __wake_oled(self):
        self.__oled.device.contrast(255)
        # self.__oled.device.show()
        self.__sleeping = False

    def __add_menu_to_list(self, menu_id):
        width, height = self.__oled.device.size
        self.__menus[menu_id] = Menu(
            menu_id, width, height, self.__oled.device.mode, self)

    def __button_locks_exist(self):
        locks_exist = False
        for filepath in listdir("/tmp"):
            if compile("pt-buttons-.*.lock").match(filepath):
                locks_exist = True
                break

        return locks_exist

    def __draw_current_menu_page_to_oled(self, force=False):
        if force:
            PTLogger.info("Forcing redraw")

        if force or self.current_menu.should_redraw():
            PTLogger.info(
                "Updating image on OLED display - "
                f"{self.current_menu.name}: {self.current_menu.page.name}"
            )

            self.current_menu.refresh()
            self.__oled.device.display(self.current_menu.image)
            self.current_menu.set_current_image_as_rendered()

    def __update_state(self):
        # TODO: move into separate class

        def __get_next_button_press_from_stack():
            button_press = ButtonPress(ButtonPress.ButtonType.NONE)
            if len(self.__button_press_stack):
                button_press = self.__button_press_stack.pop(0)
            return button_press

        def __get_page_no_to_move_to(forwards):
            if forwards:
                on_first_page = self.current_menu.page_number == 0
                return (
                    len(self.current_menu.pages) - 1
                    if on_first_page
                    else self.current_menu.page_number - 1
                )
            else:
                on_last_page = (
                    self.current_menu.page_number == len(
                        self.current_menu.pages) - 1
                )
                return 0 if on_last_page else self.current_menu.page_number + 1

        def __call_func_if_callable(func):
            if func is not None:
                func()
            return func is not None

        button_press = __get_next_button_press_from_stack()

        if button_press.event_type != ButtonPress.ButtonType.NONE:
            if self.__sleeping:
                self.__wake_oled()
                self.__current_page_frame_counter = 0
            else:
                if button_press.is_direction():
                    forwards = button_press.event_type == ButtonPress.ButtonType.UP
                    self.current_menu.page_number = __get_page_no_to_move_to(
                        forwards)
                    self.__current_page_frame_counter = 0

                elif button_press.is_action():
                    current_page = self.current_menu.page
                    if button_press.event_type == ButtonPress.ButtonType.SELECT:
                        __call_func_if_callable(
                            current_page.select_action_func)
                    else:
                        if not __call_func_if_callable(current_page.cancel_action_func):
                            if self.current_menu.parent is not None:
                                self.change_menu(self.current_menu.parent)

        max_current_hotspot_interval = self.current_menu.page.hotspot.interval
        self.__frame_sleep_time = (
            max_current_hotspot_interval
            if max_current_hotspot_interval < self.__default_frame_sleep_time
            else self.__default_frame_sleep_time
        )

        self.current_menu.refresh()
        self.__draw_current_menu_page_to_oled()

        if not self.__sleeping:
            go_to_sleep = self.__current_page_frame_counter > self.__current_page_frame_counter_limit
            if go_to_sleep:
                self.__sleep_oled()
            else:
                self.__current_page_frame_counter += self.__frame_sleep_time

    def __wait_for_oled_control(self):
        oled_control_lost_since_last_cycle = False
        while True:
            if self.__oled.is_active():
                if oled_control_lost_since_last_cycle is False:
                    PTLogger.info("User has taken control of the OLED")
                    oled_control_lost_since_last_cycle = True
                sleep(1)
            else:
                if oled_control_lost_since_last_cycle:
                    PTLogger.info("OLED control restored")
                    self.__oled.reset()
                    self.current_menu.refresh(force=True)
                    self.__draw_current_menu_page_to_oled()
                break
