import hashlib
import hmac
import os
import urllib.parse
from dataclasses import dataclass


@dataclass
class VnpayConfig:
    tmn_code: str
    hash_secret: str
    pay_url: str
    return_url: str


def _hmac_sha512(key: str, data: str) -> str:
    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha512).hexdigest()


def build_vnpay_url(*, cfg: VnpayConfig, params: dict) -> str:
    ordered = dict(sorted((k, v) for k, v in params.items() if v is not None))
    hash_data = "&".join(
        f"{urllib.parse.quote(str(key), safe='')}={urllib.parse.quote(str(value), safe='')}"
        for key, value in ordered.items()
    )
    secure_hash = _hmac_sha512(cfg.hash_secret, hash_data)
    query = f"{hash_data}&vnp_SecureHashType=HmacSHA512&vnp_SecureHash={secure_hash}"
    return f"{cfg.pay_url}?{query}"


def get_vnpay_cfg() -> VnpayConfig | None:
    tmn = os.getenv("VNPAY_TMN_CODE", "DH2F13SW").strip()
    secret = os.getenv("VNPAY_HASH_SECRET", "NXZM3DWFR0LC4R5VBK85OJZS1UE9KI6F").strip()
    pay_url = os.getenv("VNPAY_PAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html").strip()
    return_url = os.getenv("VNPAY_RETURN_URL", "http://127.0.0.1:8000/orders/vnpay/return/").strip()
    if not (tmn and secret and return_url):
        return None
    return VnpayConfig(tmn_code=tmn, hash_secret=secret, pay_url=pay_url, return_url=return_url)
