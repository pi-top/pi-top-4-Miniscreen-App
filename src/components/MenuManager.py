from time import sleep
from components.System import is_pi

if not is_pi():
    from components.helpers.ButtonPressHelper import ButtonPressHelper

from components.Menu import Menu
from components.ButtonPress import ButtonPress
from components.System import (
    device,
    got_pi_control,
)

from components.helpers.RequestClient import RequestClient
from components.helpers import MenuHelper


class MenuManager:
    """Owner class for all Menus. Handles input events and controls menu behaviour."""

    def __init__(self):
        """Constructor for MenuManager"""

        self.button_press_stack = []
        self._continue = True
        self._request_client = RequestClient()
        self._request_client.initialise(self)
        if self._request_client.start_listening() is False:
            self.stop()
            raise Exception("Unable to start listening on request client")

        self.menus = dict()
        self.add_menu_to_list(MenuHelper.Menus.SYS_INFO)
        self.add_menu_to_list(MenuHelper.Menus.MAIN_MENU)
        self.add_menu_to_list(MenuHelper.Menus.PROJECTS)

        self.change_menu(MenuHelper.Menus.SYS_INFO)

        MenuHelper.set_app(self)

    def stop(self):
        self._continue = False
        self._request_client._continue = False

    def add_menu_to_list(self, menu_id):
        self.menus[menu_id] = Menu(device, menu_id)

    def change_menu(self, menu_to_go_to):
        if menu_to_go_to in self.menus:
            self.current_menu = self.menus[menu_to_go_to]
        else:
            self.stop()
            raise Exception("Unable to find menu: " + str(menu_to_go_to))

    def add_button_press_to_stack(self, button_press_event):
        if button_press_event != ButtonPress.ButtonType.NONE:
            self.button_press_stack.append(button_press_event)

    def get_next_button_press_from_stack(self):
        button_press = ButtonPress(ButtonPress.ButtonType.NONE)
        if len(self.button_press_stack):
            button_press = self.button_press_stack.pop(0)
        return button_press

    def update_state(self):
        button_press = self.get_next_button_press_from_stack()

        if button_press.event_type != ButtonPress.ButtonType.NONE:
            if button_press.is_direction():
                new_page = None
                if button_press.event_type == ButtonPress.ButtonType.DOWN:
                    on_first_page = self.current_menu.page_index == 0
                    new_page = self.current_menu.last_page_no() if on_first_page else self.current_menu.page_index - 1
                elif button_press.event_type == ButtonPress.ButtonType.UP:
                    on_last_page = self.current_menu.page_index == self.current_menu.last_page_no()
                    new_page = 0 if on_last_page else self.current_menu.page_index + 1
                self.current_menu.move_instantly_to_page(new_page)

            elif button_press.is_action():
                if button_press.event_type == ButtonPress.ButtonType.SELECT:
                    # Do action according to page's function
                    if (
                        self.current_menu.get_current_page().select_action_func
                        is not None
                    ):
                        self.current_menu.get_current_page().select_action_func()
                elif button_press.event_type == ButtonPress.ButtonType.CANCEL:
                    if (
                        self.current_menu.get_current_page().cancel_action_func
                        is not None
                    ):
                        self.current_menu.get_current_page().cancel_action_func()
                    elif self.current_menu.parent is not None:
                        self.change_menu(self.current_menu.parent)

        self.current_menu.redraw_if_necessary()

    def main_loop(self):
        try:
            while self._continue:
                if not is_pi():
                    self.add_button_press_to_stack(ButtonPressHelper.get())
                self.update_state()
                sleep(0.1)
        except SystemExit:
            pass
