from pynput import mouse, keyboard
from pynput.mouse import Button
from pynput.keyboard import Key, KeyCode
import queue
import threading
import re

_event_queue = queue.Queue()
_callback_list = []
_state = set()
_close_event = threading.Event()


def _on_click(_x,  _y, button: mouse.Button, pressed: bool):
    if not _close_event.is_set():
        _event_queue.put((button, pressed))


def _on_press(key):
    if not _close_event.is_set():
        _event_queue.put((key, True))


def _on_release(key):
    if not _close_event.is_set():
        _event_queue.put((key, False))


def _parse(keylist):
    special_keys = re.findall(r"(\<.+?\>)", keylist)
    for key in special_keys:
        keylist = keylist.replace(key, "")
    normal_keys = keylist
    keylist = set()
    for i in normal_keys:
        try:
            keylist.add(KeyCode.from_char(i.lower()))
        except KeyError:
            print("invalid normal key")
    for i in special_keys:
        tmp: str = i[1:-1].lower()
        if "button" in tmp:
            keylist.add(Button(int(tmp[6:])))
        elif tmp in ("left", "right", "middle"):
            keylist.add(Button[tmp])
        else:
            keylist.add(Key[tmp])
    return keylist


def bind(keylist, callback, *args):
    """
    绑定热键的回调函数
    Args:
        keylist: 形如<ctrl><button9>q的字符串,代表同时按下ctrl+鼠标测键+q时调用`callback(*args)`
    """
    keylist = _parse(keylist)
    print(keylist)
    _callback_list.append((keylist, callback, args))


def unbind(keylist, callback, *args):
    """
    清除热键的回调函数, 各个参数需要与绑定时一致才可以找到并清除
    """
    keylist = _parse(keylist)
    _callback_list.remove((keylist, callback, args))


def _consumer():
    while True:
        event = _event_queue.get()
        if event is None:
            # clear
            _event_queue.task_done()
            while not _event_queue.empty():
                _event_queue.get()
                _event_queue.task_done()
            _state.clear()
            return
        if event[1]:
            _state.add(event[0])
            for i in filter(lambda x: _state == x[0], _callback_list):
                print("active", i)
                func = i[1]
                args = i[2]
                func(*args)
        if not event[1]:
            if event[0] in _state:
                _state.remove(event[0])
        _event_queue.task_done()

def key2str(key):
    try:
        key = key.name
    except:
        key = key.char
    return key

def capture_hotkey(process_callback=None, result_callback = None):
    """
    用于捕获热键，方便动态设置热键
    Args:
        process_callback: 捕获过程中的回调函数，传递捕获过程中按键集合参数
        result_callback: 传递捕获结果的回调函数
    """
    state = set()
    count = 0
    lock = threading.Lock()
    over_event = threading.Event()
    def press(key):
        if over_event.is_set():
            return False
        state.add(key2str(key))
        if process_callback:
            print(state)
            process_callback(state)
    def click(_x,  _y, button: mouse.Button, pressed: bool):
        if over_event.is_set():
            return False
        if pressed:
            state.add(key2str(button))
            if process_callback:
                print(state)
                process_callback(state)
        if not pressed:
            nonlocal count
            lock.acquire()
            count -= 1
            if len(state) + count == 0:
                lock.release()
                over_event.set()
                result_callback(state)
                return False
            lock.release()
    def release(_):
        if over_event.is_set():
            return False
        nonlocal count
        lock.acquire()
        count -= 1
        if len(state) + count == 0:
            lock.release()
            over_event.set()
            result_callback(state)
            return False
        lock.release()
    _keyboard_listener = keyboard.Listener(
            on_press=press,
            on_release=release)
    _keyboard_listener.start()
    _mouse_listener = mouse.Listener(
            on_click=click)
    _mouse_listener.start()
    return over_event, _keyboard_listener, _mouse_listener

KEYBINDER_THREAD: threading.Thread = None
KEYBOARD_LISTENER: threading.Thread = None
MOUSE_LISTENER: threading.Thread = None

def start_keybinder(daemon=True):
    """
    启动热键处理线程，只能启动一次
    Args:
        daemon: 守护线程
    """
    _close_event.clear()
    global KEYBINDER_THREAD
    global MOUSE_LISTENER
    global KEYBOARD_LISTENER
    if KEYBOARD_LISTENER is None:
        KEYBOARD_LISTENER = keyboard.Listener(
            on_press=_on_press,
            on_release=_on_release)
        KEYBOARD_LISTENER.start()
    if MOUSE_LISTENER is None:
        MOUSE_LISTENER = mouse.Listener(
            on_click=_on_click)
        MOUSE_LISTENER.start()
    KEYBINDER_THREAD = threading.Thread(target=_consumer, daemon=daemon)
    KEYBINDER_THREAD.start()
    return KEYBINDER_THREAD


def stop_keybinder():
    """
    关闭keybinder线程,不会清除绑定列表
    """
    print("stop keybinder")
    _close_event.set()
    _event_queue.put(None)
    _event_queue.join()


if __name__ == "__main__":
    # bind("<Ctrl><B9>C", lambda: print("hello"))
    # start_keybinder().join()
    print(capture_hotkey(print, print))
