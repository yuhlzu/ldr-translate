#!/usr/bin/python3
# coding: utf-8
#
# A simple indicator applet displaying cpu and memory information
#
# Author: yuh <yuhldr@gmail.com>
# Original Homepage: https://yuhldr.github.io/
# Fork Homepage: https://github.com/yuhldr/ldr-translate
# License: GPL v3

import os

import gi

from utils import locales, version, config
from utils.locales import t_ui
from utils.keybinder import start_keybinder, bind, stop_keybinder, unbind
from utils.locales import t

try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as appindicator
except ValueError:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as appindicator

try:
    gi.require_version('Keybinder', '3.0')
    from gi.repository import Keybinder
except ModuleNotFoundError as e:
    print(t("error.lib.no_Keybinder"))

gi.require_version("Gtk", "3.0")

from ui_translate import Translate
from preferences import Preference

from gi.repository import Gtk, Gdk, GdkPixbuf, GObject


def _on_help(event=None, data=None):
    logo = GdkPixbuf.Pixbuf.new_from_file_at_size("./icon/icon.png", 64, 64)

    version_home_url = version.get_value("home_url")
    version_name = version.get_value("name")

    dialog = Gtk.AboutDialog()

    dialog.set_logo(logo)
    dialog.set_license_type(Gtk.License.GPL_3_0)

    dialog.set_program_name("兰译")
    dialog.set_copyright("© 2021-2022 兰朵儿")

    dialog.set_version("V " + version_name)
    dialog.set_website(version_home_url)

    dialog.set_comments(locales.t("version.msg"))
    dialog.set_website_label(locales.t("version.home_name"))

    dialog.set_authors(["yuh"])
    # 翻译
    dialog.set_translator_credits("yuh")
    # 文档
    dialog.set_documenters(["yuh"])
    # 美工
    dialog.set_artists(["yuh"])
    dialog.connect('response', lambda dialog_, data_: dialog_.destroy())
    dialog.show_all()


def on_exit(event=None, data=None):
    try:
        Gtk.main_quit()
    except RuntimeError:
        pass


class LdrTranslate(Gtk.Application):

    def __init__(self):
        self.translate_win = None
        self._help_dialog = None
        # 翻译模式
        self.tm_s = t("ui.appindicator_label.translate_models")
        self.tm = -1

        self.clip_copy = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clip_select = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self.handler_id_clip = None

        self.indicator = appindicator.Indicator.new(
            "ldr-translate", os.path.abspath(config.get_tray_icon_file()),
            appindicator.IndicatorCategory.SYSTEM_SERVICES)
        self.indicator.set_label("翻译中", "")
        self.indicator.set_ordering_index(1)
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        Keybinder.init()
        self._create_menu()

    def _create_menu(self):
        menu = Gtk.Menu()

        pref_menu = Gtk.MenuItem(label='显示翻译窗口')
        pref_menu.connect('activate', self._active_translate_windows)
        menu.add(pref_menu)
        menu.add(Gtk.SeparatorMenuItem())

        menu_t_0 = Gtk.RadioMenuItem(label=self.tm_s[0])
        menu_t_0.connect('activate', self._set_translate_model, 0)
        menu.append(menu_t_0)
        # 默认初始化第一个
        menu_t_0.set_active(True)

        menu_t_1 = Gtk.RadioMenuItem(label=self.tm_s[1], group=menu_t_0)
        menu_t_1.connect('activate', self._set_translate_model, 1)
        menu.append(menu_t_1)

        menu_t_2 = Gtk.RadioMenuItem(label=self.tm_s[2], group=menu_t_0)
        menu_t_2.connect('activate', self._set_translate_model, 2)
        menu.append(menu_t_2)

        menu_t_3 = Gtk.RadioMenuItem(label=self.tm_s[3], group=menu_t_0)
        menu_t_3.connect('activate', self._set_translate_model, 3)
        menu.append(menu_t_3)

        menu_t_4 = Gtk.RadioMenuItem(label=self.tm_s[4], group=menu_t_0)
        menu_t_4.connect('activate', self._set_translate_model, 4)
        menu.append(menu_t_4)

        menu.add(Gtk.SeparatorMenuItem())

        menu_prf = Gtk.MenuItem(label=t_ui("setting_label"))
        menu_prf.connect('activate', self._on_preference)
        menu.add(menu_prf)

        help_menu = Gtk.MenuItem(label="关于：V" + version.get_value("name"))
        help_menu.connect('activate', _on_help)
        menu.add(help_menu)

        exit_menu = Gtk.MenuItem(label='完全退出')
        exit_menu.connect('activate', on_exit)
        menu.add(exit_menu)

        menu.show_all()
        self.indicator.set_menu(menu)
        self._active_translate_windows()

    def _on_preference(self, event=None, data=None):
        Preference(self)

    def _set_translate_model(self, view=None, n=0):
        if self.tm == n:
            return

        # 全部关闭重新来
        if self.tm in (3, 4):
            unbind(config.get_config_setting("key_gtk"), app.key_binder_callback)
            stop_keybinder()

        if self.handler_id_clip is not None:
            self.get_clipboard().disconnect(self.handler_id_clip)
            self.handler_id_clip = None

        self.tm = n
        if n in (0, 1):
            self.handler_id_clip = self.get_clipboard().connect(
                "owner-change", self._active_translate_windows)
        elif n in (3, 4):
            bind(config.get_config_setting("key_gtk"), app.key_binder_callback)
            start_keybinder()

        self.indicator.set_label(self.tm_s[self.tm], "")

    def _open_translate_windows(self):
        if self.translate_win is None or self.translate_win.is_hide:
            self.translate_win = Translate()
            self.translate_win.open()

    def _active_translate_windows(self, clipboard=None, eventOwnerChange=None):
        self._open_translate_windows()
        if eventOwnerChange is None:
            clipboard = None
        self.translate_win.copy_auto_translate(clipboard)

    def key_binder_callback(self):
        def gui_callback():
            self._open_translate_windows()
            if self.tm == 3:
                self.translate_win.copy_auto_translate(self.clip_copy)
            if self.tm == 4:
                self.translate_win.copy_auto_translate(self.clip_select)
        GObject.idle_add(gui_callback)

    def get_clipboard(self):
        if self.tm == 0:
            return self.clip_copy
        elif self.tm == 1:
            return self.clip_select


# ******* 监测  *******

if __name__ == "__main__":

    app = LdrTranslate()
    try:
        Gtk.main()
    except KeyboardInterrupt:
        on_exit()
