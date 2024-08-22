import threading

from gi.repository import Gtk, GLib, GObject

from api import translate
from api.server import baidu, tencent
from api.server_config import server_baidu, server_tencent, get_api_key
from utils import config, version
from utils.keybinder import capture_hotkey


def on_cbb_tray_icon(combo):
    config.set_tray_icon(combo.get_active_text())


def update_autostart(menu_check):
    config.update_autostart(menu_check.get_active())


def update_ocr_local(menu_check):
    config.set_ocr_local(menu_check.get_active())


def update_del_wrapping(menu_check):
    config.set_del_wrapping(menu_check.get_active())

def get_text(text_view):
    tb = text_view.get_buffer()
    text = tb.get_text().strip()

    return text


def save_server(tv_a, tv_b, lb_msg, server, is_ocr=False):
    text_a = get_text(tv_a)
    text_b = get_text(tv_b)

    def _save(text_a_, text_b_):
        ok, text_a_, text_b_ = translate.check_server_api(
            (is_ocr, server, text_a_, text_b_))

        msg = "超时或账号密码错误"

        tv_a.set_text(text_a_)
        tv_b.set_text(text_b_)

        if ok:
            msg = "成功，已保存"
            key_a, key_b = get_api_key(server, is_ocr)
            config.set_config(server, key_a, text_a_)
            config.set_config(server, key_b, text_b_)
        lb_msg.set_text(msg)

    def _save_c(text_a_, text_b_):
        GLib.idle_add(_save, text_a_, text_b_)

    if len(text_a) == 0 or len(text_b) == 0:
        lb_msg.set_text("已恢复默认（不推荐）")
    else:
        lb_msg.set_text("加载中...")
        tt = threading.Thread(target=_save_c, args=(
            text_a,
            text_b,
        ))
        tt.start()


class Preference(Gtk.ApplicationWindow):

    def __init__(self, parent):
        Gtk.Window.__init__(self)
        self.set_border_width(10)
        self.set_default_size(400, 360)
        self.set_keep_above(True)
        self.set_title("翻译设置")
        self.set_icon_from_file('./icon/setting.svg')
        self.ind_parent = parent

        ui = Gtk.Builder()
        ui.add_from_file('./preference.ui')

        self.cbb_tray_icon = ui.get_object('cbb_tray_icon')
        self.lb_sys_msg = ui.get_object('lb_sys_msg')
        self.lb_version_msg = ui.get_object('lb_version_msg')
        self.init_other(ui)

        self.tv_baidu_translate_app_id = ui.get_object('tv_baidu_translate_app_id')
        self.tv_baidu_translate_secret_key = ui.get_object('tv_baidu_translate_secret_key')
        self.lb_baidu_translate_msg = ui.get_object('lb_baidu_translate_msg')
        self.tv_baidu_ocr_app_key = ui.get_object('tv_baidu_ocr_app_key')
        self.tv_baidu_ocr_secret_key = ui.get_object('tv_baidu_ocr_secret_key')
        self.lb_baidu_ocr_msg = ui.get_object('lb_baidu_ocr_msg')
        self.init_baidu_api(ui)

        self.tv_tencent_secret_id = ui.get_object('tv_tencent_secret_id')
        self.tv_tencent_secret_key = ui.get_object('tv_tencent_secret_key')
        self.lb_tencent_msg = ui.get_object('lb_tencent_msg')
        self.init_tencent(ui)

        self.add(ui.get_object('gd_prf'))
        self.show_all()

    def init_other(self, ui):
        cbtn_auto_start = ui.get_object('cbtn_auto_start')
        cbtn_auto_start.set_active(config.get_autostart())
        cbtn_auto_start.connect('toggled', update_autostart)

        cb_ocr_local = ui.get_object('cb_ocr_local')
        cb_ocr_local.set_active(config.is_ocr_local())
        cb_ocr_local.connect('toggled', update_ocr_local)

        cbt_del_wrapping = ui.get_object("cbtn_del_wrapping")
        cbt_del_wrapping.set_active(config.if_del_wrapping())
        cbt_del_wrapping.connect("toggled", update_del_wrapping)

        self.lb_version_msg.set_markup(version.get_default())

        hotkey_text = ui.get_object("hotkey")
        hotkey_text.get_buffer().set_text(config.get_config_setting("key_gtk"))
        hotkey_text.connect("button-release-event", self.set_hotkey, None)
        self.hotkey_set_flag = False
        ui.get_object('btn_update').connect('clicked', self.check_update)

        for tray_type in config.get_tray_types():
            self.cbb_tray_icon.append_text(tray_type)

        self.cbb_tray_icon.set_active(config.get_tray_icon_n())
        self.cbb_tray_icon.connect("changed", on_cbb_tray_icon)

    def set_hotkey(self, widget, event, user_data):
        if event.button == 1 and not self.hotkey_set_flag:
            print("hotkey flag")
            widget.get_buffer().set_text("设置热键中...")
            self.hotkey_set_flag = True
            def to_str(stat):
                string = ""
                for i in stat:
                    if len(i) == 1:
                        string += i
                    else:
                        string += "<%s>" %i
                return string
            
            def change_text(stat):
                widget.get_buffer().set_text(to_str(stat))
            print("start")
            def do_result(s):
                config.set_config(config.config_sections_setting, "key_gtk", to_str(s))
                print("set hotkey %s"% to_str(s))
                self.hotkey_set_flag = False

            capture_hotkey(lambda s: GObject.idle_add(change_text, s), do_result)

    def init_baidu_api(self, ui):
        def set_value(tv, key):
            tv.set_text(config.get_value(server_baidu, key))

        ui.get_object('btn_baidu_translate_save').connect(
            "clicked", self.save_baidu_translate)
        ui.get_object('btn_baidu_ocr_save').connect("clicked",
                                                    self.save_baidu_ocr)

        set_value(self.tv_baidu_translate_app_id, "translate_app_id")
        set_value(self.tv_baidu_translate_secret_key, "translate_secret_key")
        set_value(self.tv_baidu_ocr_app_key, "ocr_api_key")
        set_value(self.tv_baidu_ocr_secret_key, "ocr_secret_key")

        url_translate = "<a href='" + baidu.how_get_url_translate + "'>如何获取？</a>"
        url_ocr = "<a href='" + baidu.how_get_url_ocr + "'>如何获取？</a>"

        ui.get_object('lb_baidu_translate_way').set_markup(url_translate)
        ui.get_object('lb_baidu_ocr_way').set_markup(url_ocr)

    def init_tencent(self, ui):
        def set_value(tv, key):
            tv.set_text(config.get_value(server_tencent, key))

        set_value(self.tv_tencent_secret_id, "translate_secret_id")
        set_value(self.tv_tencent_secret_key, "translate_secret_key")

        url = "<a href='" + tencent.how_get_url_translate + "'>如何获取？</a>"
        ui.get_object('lb_tencent_way').set_markup(url)

        ui.get_object('btn_tencent_save').connect("clicked", self.save_tencent)

    def save_baidu_translate(self, btn=None):
        save_server(
            self.tv_baidu_translate_app_id,
            self.tv_baidu_translate_secret_key,
            self.lb_baidu_translate_msg,
            server_baidu,
        )

    def save_baidu_ocr(self, btn=None):
        server = server_baidu

        config.set_config(server, "access_token", "")
        config.set_config(server, "expires_in_date", 0)

        save_server(self.tv_baidu_ocr_app_key,
                    self.tv_baidu_ocr_secret_key, self.lb_baidu_ocr_msg,
                    server, True)

    def save_tencent(self, btn=None):
        save_server(self.tv_tencent_secret_id, self.tv_tencent_secret_key,
                    self.lb_tencent_msg, server_tencent)

    def check_update(self, view=None):
        def _check():
            s, msg = version.check_update()
            self.lb_version_msg.set_markup(s)

        self.lb_version_msg.set_markup("更新检查中……")

        tt = threading.Thread(target=_check)
        tt.start()
