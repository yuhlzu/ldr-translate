import base64
import hashlib
import json
import random
import re
import time
import urllib

import requests

from utils.locales import t

try:
    from cryptography.hazmat.backends import openssl
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ModuleNotFoundError as e:
    print(t("error.lib.no_cryptography"))

from api import server_config
from utils import config

config_server = server_config.server_youdao
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.57",
    "Origin": "https://fanyi.youdao.com",
    "Referer": "https://fanyi.youdao.com/",
})
fixed_value = None
interface_select = 1


def sign(key, _time=None):
    _time = _time if _time is not None else int(time.time() * 1000)
    print(_time)
    hash_md5 = hashlib.md5()
    input_string = "client=fanyideskweb&mysticTime={}&product=webfanyi&key={}".format(
        _time, key)
    hash_md5.update(input_string.encode('utf-8'))
    return hash_md5.hexdigest()


def get_fixed_value():
    index_url = "https://fanyi.youdao.com/index.html"
    res = session.get(index_url).text
    js = re.findall(r'src="(js/app\..+?\.js)"', res)
    if len(js) != 1:
        print("get js url error")
        return None
    url = "https://fanyi.youdao.com/" + js[0]
    js = session.get(url).text
    first_sign_key = r'webfanyi-key-getter".+?a\s*=\s*"(\w+)'
    decode_key = r'decodeKey:\s*"(.+?)"'
    decode_iv = r'decodeIv:\s*"(.+?)"'
    first_sign_key = re.findall(first_sign_key, js)
    decode_key = re.findall(decode_key, js)
    decode_iv = re.findall(decode_iv, js)
    if len(first_sign_key) != 1:
        print("get secret key value error:", first_sign_key)
        return None
    if len(decode_key) != 1:
        print("get decode key value error:", decode_key)
        return None
    if len(decode_iv) != 1:
        print("get decode iv value error:", decode_iv)
        return None
    cookie_url = "https://dict.youdao.com/login/acc/query/accountinfo"
    res = session.get(cookie_url)
    session.cookies.set("OUTFOX_SEARCH_USER_ID_NCOO",
                        str(2147483647 * random.random()))
    session.cookies.set("OUTFOX_SEARCH_USER_ID", res.cookies.get_dict()[
                        'OUTFOX_SEARCH_USER_ID'])
    print(session.cookies.get_dict())
    return {
        'secret_key': first_sign_key[0],
        'decode_key': decode_key[0],
        'decode_iv': decode_iv[0]
    }


def get_translate_secret_key():
    url = "https://dict.youdao.com/webtranslate/key"
    global fixed_value
    if fixed_value is None:
        fixed_value = get_fixed_value()
        if fixed_value is None:
            print("get fixed value failed")
            return None

    now_time = int(time.time() * 1000)
    params = {
        "keyid": "webfanyi-key-getter",
        "sign": sign(fixed_value['secret_key'], now_time),
        "client": "fanyideskweb",
        "product": "webfanyi",
        "appVersion": "1.0.0",
        "vendor": "web",
        "pointParam": "client,mysticTime,product",
        "mysticTime": now_time,
        "keyfrom": "fanyi.web"
    }
    res = session.get(url, params=params)
    translate_secret_key: dict = res.json()
    if translate_secret_key['code'] == 0:
        return translate_secret_key['data']['secretKey']
    else:
        print("get translate secret key failed", params)
        return None


def translate_interface_2(s, from_lang="auto", to_lang=""):
    url = "http://fanyi.youdao.com/translate?&doctype=json&type=%s&i=%s"
    url = url % (from_lang + "2" + to_lang, urllib.parse.quote(s))

    s1 = ""
    request = requests.get(url, timeout=config.time_out)
    if request.status_code == 200:
        result = request.json()

        if "errorCode" in result and result["errorCode"] != 0:
            ok = False
            s1 = "翻译错误,试试其他引擎?"
        else:
            print(result["translateResult"])
            for line in result["translateResult"]:
                for sentence in line:
                    s1 += sentence["tgt"]
                s1 += '\n'
    else:
        s1 = "请求错误：" + request.content

    return s1


def translate_interface_1(s, from_lang="auto", to_lang=""):
    url = "https://dict.youdao.com/webtranslate"
    sk = get_translate_secret_key()
    if sk is None:
        return None
    _time = int(time.time() * 1000)
    res = session.post(url, data={
        "i": s,
        "from": from_lang,
        "to": to_lang,
        "domain": "0",
        "dictResult": True,
        "keyid": "webfanyi",
        "sign": sign(sk, _time),
        "client": "fanyideskweb",
        "product": "webfanyi",
        "appVersion": "1.0.0",
        "vendor": "web",
        "pointParam": "client,mysticTime,product",
        "mysticTime": _time,
        "keyfrom": "fanyi.web"
    }).text
    try:
        res = decode_translate(res)
    except Exception as e:
        print('decrypt translation message failed', e)
        return None
    print(res)
    tmp = ""
    if res['code'] != 0:
        return s
    trans_res = res.get('translateResult', None)
    if trans_res is not None:
        for line in trans_res:
            # 有道接口数据已提供段落换行符号
            for sentence in line:
                tmp += sentence['tgt']
        tmp += '\n'
    dict_res = res.get('dictResult', None)
    if dict_res is not None and dict_res.get("ec", None) is not None:
        word = dict_res['ec']['word']
        phones = map(lambda x: "{}: /{}/".format(
            x[:x.find('p')], word[x]), filter(lambda x: "phone" in x, word.keys()))
        tmp += "  ".join(phones) + '\n'
        for description in word['trs']:
            tmp += description.get("pos", "") + ' ' + description.get('tran', "") + '\n'
        wfs = word.get("wfs", None)
        if wfs is not None:
            for wf in wfs:
                tmp += wf['wf']['name'] + ':' + wf['wf']['value'] + '\n'
    return tmp


def translate_text(s, from_lang="auto", to_lang=""):
    global interface_select
    if interface_select == 1:
        res = translate_interface_1(s, from_lang, to_lang)
        if res is None:
            interface_select += 1
            return "接口错误，已自动切换接口"
    elif interface_select == 2:
        res = translate_interface_2(s, from_lang, to_lang)
    return res


def decode_translate(text):
    md5 = hashlib.md5()
    key = fixed_value['decode_key']
    md5.update(key.encode("utf-8"))
    key = md5.digest()
    md5 = hashlib.md5()
    iv = fixed_value['decode_iv']
    md5.update(iv.encode("utf-8"))
    iv = md5.digest()
    print(key, iv)
    # 创建AES CBC解密器对象并解密数据
    print("text length:", len(text))
    input_bytes = base64.urlsafe_b64decode(text)
    print("bytes length:", len(input_bytes))
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), openssl.backend)
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(input_bytes) + decryptor.finalize()
    # 使用PKCS5填充解密的数据
    padder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    unpadded_data = padder.update(decrypted_data) + padder.finalize()
    res = unpadded_data.decode("utf-8")
    res = json.loads(res)
    return res


if __name__ == "__main__":
    translate_text("Flow")
