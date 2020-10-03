from collections import defaultdict
from typing import Set, List, Optional

from lxml import html
from lxml.html import HtmlElement

HEAD_COLUMN_TAG = 'th'


def get_html_from_string(value: str) -> HtmlElement:
    return html.fromstring(value)


def format_tag_text(text: str) -> str:
    if text is None:
        text = str(text)
    text = text.strip()
    return text.replace('\n', '')


def parse_table_thead(head: str, tag_text_key: str, attributes: Set[str]):
    """
    Парсит заголовок таблицы и собирает дикт-хелпер для получения индекса колонки по её
    search-паттерну (это может быть как видимый текст, так и значение какого-либо атттрибута)
    :param head:
    :param tag_text_key:
    :param attributes:
    :return:
    """
    res = defaultdict(dict)
    index = 1
    parsed_head: HtmlElement = get_html_from_string(head)
    tr_element: Optional[HtmlElement] = None

    if parsed_head.tag == 'div':
        # внутри thead есть что-то еще кроме одного tr со всеми заголовками
        for item in parsed_head.iterchildren():
            if item.tag == 'tr':
                tr_element = item
                break
    elif parsed_head.tag == 'tr':
        tr_element = parsed_head

    if tr_element is None:
        raise ValueError('Table format could be changed')

    for item in tr_element.iterchildren():
        if item.tag == HEAD_COLUMN_TAG:
            formatted_key = format_tag_text(item.text)
            if tag_text_key in res and formatted_key in res[tag_text_key]:
                raise ValueError(f'Duplicate value={formatted_key} of th.text in header of table')
            res[tag_text_key][formatted_key] = index
            if attributes:
                for name, value in item.items():
                    if value and name in attributes:
                        res[name][value] = index
            index += 1
    return res


def parse_table_row(row: str) -> List:
    """
    Парсит строку таблицы (содержимое tr) в список (вытаскивает визуальное значение ячеек)
    :param row:
    :return:
    """
    res = []
    obj: HtmlElement = get_html_from_string(row)
    if obj.tag != 'tr':
        raise ValueError('It parse only tr tag content')
    for cell in obj.iterchildren():
        res.append(cell.text.strip() if cell.text else None)
    return res


def parse_table_cell(row: str) -> Optional[str]:
    """
    Парсит ячейку таблицы (содержимое td) и вытаскивает из неё видимый текст
    :param row:
    :return:
    """
    cell: HtmlElement = get_html_from_string(row)
    if cell.tag != 'td':
        raise ValueError('It parse only td tag content')
    return cell.text.strip() if cell.text else None


def format_xpath_from_parent(xpath: str):
    """
    Возвращает xpath, относительно родителя
    :param xpath:
    :return:
    """
    if xpath.startswith('//'):
        xpath = xpath.replace('//', '/', 1)
    return f'./{xpath}'
