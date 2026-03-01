from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "dombot" / "domain_utils.py"
_SPEC = spec_from_file_location("domain_utils_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
canonicalize_domain = _MODULE.canonicalize_domain


def test_canonicalize_domain_www_url():
    assert canonicalize_domain("https://www.walmart.com/product/123") == "walmart.com"


def test_canonicalize_domain_with_port_and_no_scheme():
    assert canonicalize_domain("WWW.GOOGLE.COM:443/search?q=test") == "google.com"


def test_canonicalize_domain_multi_part_suffix():
    assert canonicalize_domain("https://api.service.co.uk/path") == "service.co.uk"


def test_canonicalize_domain_localhost():
    assert canonicalize_domain("localhost:8000") == "localhost"


def test_canonicalize_domain_ip_address():
    assert canonicalize_domain("http://192.168.1.11:5000") == "192.168.1.11"
