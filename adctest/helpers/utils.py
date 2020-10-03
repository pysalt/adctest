from typing import List, Dict, Optional, Tuple
from urllib.parse import urlsplit, urlencode, parse_qs


def get_parents_classes_attrs(bases):
    all_attrs = {}
    attrs_dict = {}

    for parent_class in reversed(bases):
        attrs_dict.update(parent_class.__dict__)

    for key, value in attrs_dict.items():
        if key.startswith('__') or callable(value):
            continue
        all_attrs[key] = value

    return all_attrs


def split_url_and_params(url: str) -> Tuple[str, str]:
    res = urlsplit(url)
    if not res.scheme:
        return url, ''
    base_url = f'{res.scheme}://{res.netloc}'
    if res.path:
        base_url = ''.join([base_url, res.path])
    return base_url, res.query or ''


def get_domain_from_url(url: str) -> str:
    res = urlsplit(url)
    return res.netloc


def get_base_url(url: str) -> str:
    base_url, _ = split_url_and_params(url=url)
    return base_url


def add_url_params(url: str, params: Dict) -> str:
    if not params:
        return url
    encoded_params = urlencode(params)
    delimiter = '&' if '?' in url else '?'
    return f'{url}{delimiter}{encoded_params}'


def format_id(id_form: str, default=None) -> Optional[int]:
    try:
        return int(id_form.strip())
    except Exception:
        return default


def get_id_from_url(url: str) -> Optional[int]:
    """
    пытается найти id объекта в ссылке по REST-схеме
    :return:
    """
    res = urlsplit(url)
    if res.query:
        params = parse_qs(res.query)
        if 'id' in params:
            return format_id(params['id'][0])
    if res.path:
        return format_id(res.path.split('/')[-1])


def get_param_from_url(url: str, param_name: str) -> Optional[List[str]]:
    """
    Возвращает параметр из url, если он есть
    :param url:
    :param param_name:
    :return:
    """
    res = urlsplit(url)
    if res.query:
        params = parse_qs(res.query)
        if param_name in params:
            return params[param_name]


def format_to_regex(value: str) -> str:
    return value.replace('.', r'\.')
