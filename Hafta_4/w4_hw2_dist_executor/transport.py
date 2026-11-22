"""transport.py — BİL 427 HW2: koordinatörün HTTP istemcisi (VERİLEN KOD).

Bu dosyayı değiştirmeyin. Her çağrı yeni bir TCP bağlantısı açar, tek bir
istek gönderir, yanıtı okur ve bağlantıyı kapatır.

Hata durumları istisna (exception) olarak yükselir:
    TimeoutError     : bağlantı kurulamadı ya da yanıt `timeout` saniyede gelmedi
    ConnectionError  : bağlantı reddedildi ya da yanıt gelmeden kapandı
                       (ConnectionRefusedError, ConnectionResetError ve
                       http.client.RemoteDisconnected bunun alt sınıflarıdır)
Bir HTTP durum kodu (ör. 409, 503) istisna DEĞİLDİR; (durum, gövde) olarak döner.
"""
import http.client
import json
from urllib.parse import urlsplit


def _request(method, url, body, timeout):
    parts = urlsplit(url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)
    try:
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn.request(method, parts.path or "/", body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        payload = json.loads(raw) if raw else None
        return resp.status, payload
    finally:
        conn.close()


def put_json(url, body, timeout):
    """PUT isteği gönderir; (durum_kodu, json_gövde) döndürür."""
    return _request("PUT", url, body, timeout)


def get_json(url, timeout):
    """GET isteği gönderir; (durum_kodu, json_gövde) döndürür."""
    return _request("GET", url, None, timeout)
