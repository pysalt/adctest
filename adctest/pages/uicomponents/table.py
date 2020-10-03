from enum import Enum
from typing import Optional, List, Dict, Set

from adctest.config import config
from adctest.helpers.exceptions import BaseTableException, TableElementNotFound, TableRowNotFound, \
    TableColumnNotFound
from adctest.pages import WebElementProxy
from adctest.pages.uicomponents.helpers.parsers import parse_table_thead, parse_table_row, parse_table_cell
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

TABLE_TAG = config.DEFAULT_TABLE_TAG
TABLE_ATTRIBUTE = config.TABLE_E2E_ATTRIBUTE
HEAD_COLUMN_TAG = 'th'


class SearchBy(Enum):
    """
    Возможные варианты поиска колонки в таблице
    """
    visible_name = 1
    """по части видимого имени"""
    attribute_name = 2
    """по имени атрибута"""


class Column:
    """
    Класс, реализующий интерфейс к колонке таблицы
    """
    head_tag_name: str = HEAD_COLUMN_TAG
    """тэг, внутри таблицы, в котором находится значение заголовка конкретной колонки"""
    _attr_name: str = None
    """имя атрибута таблицы, в котором находится инстанс Column"""
    visible_name: str = None
    """видимое имя колонки (по умолчанию именно по этому атрибуту происходит поиск колонки в таблице)"""
    search_attr_name: str = None
    """дополнительный способ поиска колонки по её атрибуту (значение атрибута должно быть уникальным)"""
    search_attr_value: str = None
    """значение атрибута колонки"""
    table = None
    """родительская таблица, с которой связана колонка"""
    relative_xpath: str = None
    """xpath относительно родительской таблицы, чтобы найти колонку"""

    def __init__(self, visible_name: str, search_type: SearchBy = SearchBy.visible_name,
                 attr_name: Optional[str] = None, attr_value: Optional[str] = None):
        """

        :param visible_name: текст, указанный в заголовке колонки
        :param search_type: тип поиска (по умолчанию поиск идет по имени колонки)
        :param attr_name: дополнительный атрибут по которому можно найти колнку (указывать, если заголовок колонки
        является неуникальным)
        :param attr_value: значение атрибута
        """
        self.visible_name = visible_name
        if search_type is SearchBy.visible_name:
            self.relative_xpath = self._compile_xpath_by_visible_name(self.visible_name)
        elif search_type is SearchBy.attribute_name:
            self.relative_xpath = self._compile_xpath_by_attribute_name(attr_name, attr_value)
            self.search_attr_name = attr_name
            self.search_attr_value = attr_value
        else:
            raise NotImplementedError(f'search_type {search_type} not implemented')

    @classmethod
    def _compile_xpath_by_visible_name(cls, name: str):
        return f'//{cls.head_tag_name}[contains(text(),"{name}")]'

    def _compile_xpath_by_attribute_name(self, name: str, value: str):
        if not (value and name):
            raise BaseTableException('attr_name and attr_value must be pass if search_type is attribute_name')
        return f'//{self.head_tag_name}[@{name}="{value}"]'

    def __repr__(self):
        return f'Column({self.relative_xpath})'

    def __set_name__(self, owner, name):
        if not issubclass(owner, Table):
            raise RuntimeError(f'Column object must be attribute of Table obj. Current parent is {owner}')
        self._attr_name = name

    def _set_parent(self, table):
        if not self._attr_name:
            raise BaseTableException('Column object must be attribute of Table obj')

        existing = getattr(self, 'table', None)
        if existing is not None and existing is not table:
            raise BaseTableException(f"Column object '{self._attr_name}' already assigned to Table '{existing}'")

        if self.search_attr_name:
            table._head_search_attrs.add(self.search_attr_name)

        self.table = table

    def __call__(self, search_value: str) -> List[WebElementProxy]:
        """
        найти все ячейки в колонке, содержащие часть строки search_value
        использование column(<искомый_видимый_текст>)
        :param search_value:
        :return:
        """
        return self.table._find_column_cells_by_visible_text(self, search_value)

    def __getitem__(self, item: int) -> WebElementProxy:
        """
        Возвращает ячейку колонки по её номеру (нумерация начинается с 1)
        Использование: column[<номер_строки_в_колонке>]
        :param item:
        :return:
        """
        if not isinstance(item, int) or item < 1:
            raise BaseTableException('Column item index must be integer >= 1')
        return self.table._get_column_cell_by_index(self, item)

    def values(self) -> List:
        """
        Возвращает все значения колонки (в порядке от заголовка)
        :return:
        """
        return self.table._get_column_values(self)

    @property
    def index(self):
        """
        Номер колонки в таблице по порядку слева направо (нумерация с 1)
        :return:
        """
        return self.table.get_column_index(self)
    
    def click(self):
        """
        Нажать на заголовок колонки. В основном для сортировки
        :return: 
        """
        cell: WebElementProxy = self.table.get_item_by_xpath(self.relative_xpath)
        cell.click_and_wait()


class TableMeta(type):
    """
    Мета-класс для Table, реализующий поиск атрибутов-колонок в сабклассах и собирающий их в _columns атрибут
    """
    def __new__(mcs, class_name, bases, attrs):
        if class_name != 'Table':
            columns = {}
            base_table = None
            for cls_ in bases:
                if cls_.__name__ == 'Table':
                    base_table = cls_
                    break

            if not base_table:
                raise BaseTableException(f'class<{class_name}> must be inheriting from Table')

            for name, item in attrs.items():
                if not name.startswith('__') and name in base_table.__dict__:
                    raise BaseTableException(f'Attribute with name="{name}" overrides parent Table attribute')
                if item is not None:
                    try:
                        item._set_parent
                    except AttributeError:
                        continue
                    else:
                        columns[name] = item

            attrs['_columns'] = columns

        table = type.__new__(mcs, class_name, bases, attrs)

        return table


class Table(metaclass=TableMeta):
    """
    Класс, предоставляющий методы по манипулированию таблицами.
    Использовать только в определении классов страниц, иначе не будет работать
    (т.к. работает по протоколу дескрипторов)
    """
    _tag_name = None
    """тэг-таблицы"""
    __attr_name = None
    """имя атрибута базовой страницы, в котором хранится инстанс таблицы"""
    page = None
    """ссылка на экземпляр страницы, на которой находится таблица"""
    _table: WebElementProxy = None
    """таблица, как WebElement селениума, предоставляет доступ к интерфейсу селениума (например, для поиска)"""

    search_by = By.XPATH
    """тип локатора для поиска таблицы на странице"""
    value = None
    """значение локатора"""

    _columns: Dict[str, Column] = None
    """закэшированные колонки"""
    _head_search_attrs: Set[str] = None
    """атрибуты head-элементов, по которым потребуется поиск"""
    columns_indexes: Dict[str, Dict[str, int]] = None
    """Найденные при инициализации таблицы индексы для колонок"""
    real_column_count: int = 0
    """Количество реально найденных колонок таблицы"""
    _head_tag_text_key: str = 'text'
    """ключ, для видимого текста тэга, по которому можно получить его индекс из _head_search_attrs"""

    r_xpath_body = '//tbody'
    r_xpath_header = '//thead'
    r_xpath_rows = '//tr'
    r_xpath_cells = '/td'

    @classmethod
    def r_xpath_row(cls, index: int):
        """
        нумерация идет с 1
        :param index:
        :return:
        """
        return f'{cls.r_xpath_rows}[{index}]'

    @classmethod
    def r_xpath_column(cls, index: int):
        """
        нумерация идет с 1
        :param index:
        :return:
        """
        return f'{cls.r_xpath_rows}{cls.r_xpath_cells}[{index}]'

    @classmethod
    def r_xpath_cell(cls, row_index: int, column_index: int):
        """
        нумерация идет с 1
        :param row_index:
        :param column_index:
        :return:
        """
        return f'{cls.r_xpath_row(row_index)}{cls.r_xpath_cells}[{column_index}]'

    @classmethod
    def r_xpath_column_cells_contains_text(cls, column_index: int, text: str):
        return f'{cls.r_xpath_rows}{cls.r_xpath_cells}[contains(text(),"{text}") and {column_index}]'

    @classmethod
    def get_body_row_xpath(cls, index: int):
        return ''.join([cls.r_xpath_body, cls.r_xpath_row(index)])

    @classmethod
    def get_header_xpath(cls, index: int):
        return ''.join([cls.r_xpath_header, cls.r_xpath_row(index)])

    @classmethod
    def get_body_cell_row_xpath(cls, row_index: int, column_index: int):
        paths = [cls.r_xpath_body, cls.r_xpath_row(row_index), cls.r_xpath_cell(row_index, column_index)]
        return ''.join(paths)

    def __repr__(self):
        return f'Table({self._tag_name}, {self.value})'

    def __init__(self, search_value: str = None, search_attribute: str = TABLE_ATTRIBUTE,
                 tag_name: str = TABLE_TAG):
        """
        Всегда возвращает первую таблицу, найденную по заданным параметрам
        :param search_value: значение атрибута для поиска
        :param search_attribute: дополнительный атрибут, по которому искать таблицу
        :param tag_name: тэг, в который закллючена таблица
        """
        if self.__class__ == Table:
            raise BaseTableException('You must inherit from Table class. Do not use directly')
        self._head_search_attrs = set()
        self._tag_name = tag_name
        if search_value and not search_attribute:
            raise BaseTableException('search_attribute and search_value must be set together')

        self.value = self._compile_search_xpath(search_attribute, search_value)
        self.init_columns()

    def _compile_search_xpath(self, attribute: str = None, value: str = None) -> str:
        if not value:
            return f"//{self._tag_name}"
        return f'//{self._tag_name}[@{attribute}="{value}"]'

    def __set_name__(self, owner, name):
        self.__attr_name = name

    def __get__(self, page, objtype=None):
        if page is None:
            return self
        page.check_opened()

        cached_attrs = page._cached_attrs
        if cached_attrs.get(self.__attr_name) is None:
            self.page = page
            self._table = self._search_table(page)
            self._parse_header()
            cached_attrs[self.__attr_name] = self
        return cached_attrs[self.__attr_name]

    def __getattr__(self, item):
        # часть магии происходит здесь, таблица часть вызовов прокидывает в свою родительскую страницу
        if self.page:
            return getattr(self.page, item)
        raise BaseTableException(f'{self.__class__.__name__} not initialized from Page object')

    def _search_table(self, page):
        table = page._find_element(self.search_by, self.value)
        return WebElementProxy(
            target_object=table,
            page=page,
            by=self.search_by,
            value=self.value,
            attr_name=self.__attr_name,
        )

    def _parse_header(self):
        head_html = self._table.find_element_by_xpath(f'.{self.r_xpath_header}').get_attribute('innerHTML')
        self.columns_indexes = parse_table_thead(head_html, self._head_tag_text_key, self._head_search_attrs)
        self.real_column_count = len(self.columns_indexes.get(self._head_tag_text_key) or [])

    def get_column_index(self, column: Column) -> int:
        """
        Возвращает индекс колонки по видимому тексту тэга, либо по значению его атрибута.
        Значение атрибута приоритетно
        :param column
        :return:
        """
        if column.search_attr_value:
            return self.columns_indexes.get(column.search_attr_name, {}).get(column.search_attr_value)
        col_index = self.columns_indexes.get(self._head_tag_text_key, {}).get(column.visible_name)

        if not col_index:
            raise BaseTableException(f'Cannot find index of {column} in {self}')

        return col_index

    def _get_column_cell_by_index(self, column: Column, row_index: int) -> WebElementProxy:
        col_index = self.get_column_index(column)
        xpath = self.r_xpath_cell(
            row_index=row_index,
            column_index=col_index,
        )
        return self.get_item_by_xpath(xpath)

    def _find_column_cells_by_visible_text(self, column: Column, text: str) -> List[WebElementProxy]:
        """
        находит все элементы колонки, которые соответсвуют переданному тексту
        :param column:
        :param text:
        :return:
        """
        col_index = self.get_column_index(column)
        xpath = self.r_xpath_column_cells_contains_text(col_index, text)
        return self.get_items_by_xpath(xpath)

    def get_header_values(self, index: int = 1) -> List:
        """
        Возвращет значения колонок заголовка таблицы
        :param index:
        :return:
        """
        return self._get_row_values_by_index(index, for_header=True)

    def get_row_values_by_index(self, index: int) -> List:
        """
        Возвращет значение строки таблицы по ей индексу (нумерация с 1, заголовок не включается)
        :param index:
        :return:
        """
        return self._get_row_values_by_index(index)

    def _get_row_values_by_index(self, index: int, for_header: bool = False) -> List:
        xpath = self.get_header_xpath(index) if for_header else self.get_body_row_xpath(index)
        try:
            row_html = self.get_item_by_xpath(xpath).get_attribute('outerHTML')
        except TableElementNotFound:
            raise TableRowNotFound(f'Row with index {index} not found in table')
        return parse_table_row(row_html)

    def get_column_values_by_index(self, index: int) -> List:
        """
        Возвращает значения колонки по её индексу
        :param index:
        :return:
        """
        if index > self.real_column_count:
            raise TableColumnNotFound(f'Column with index {index} not exists in table')
        xpath = self.r_xpath_column(index)
        try:
            cells = self.get_items_by_xpath(xpath)
        except TableElementNotFound:
            cells = []

        res: List = [parse_table_cell(c.get_attribute('outerHTML')) for c in cells]
        return res

    def _get_column_values(self, column: Column) -> List:
        """
        Возвращает все значения колонки
        :param column:
        :return:
        """
        col_index = self.get_column_index(column)
        return self.get_column_values_by_index(col_index)

    def init_columns(self):
        for item in self._columns.values():
            item._set_parent(self)

    def get_item_by_xpath(self, xpath: str) -> WebElementProxy:
        """
        находит первый элемент таблицы по xpath (он должен быть относительно тэга таблицы)
        :param xpath:
        :return:
        """
        xpath = ''.join([self.value, xpath])
        try:
            el = self._table.find_element_by_xpath(xpath)
        except NoSuchElementException:
            raise TableElementNotFound(f'Element not found by {By.XPATH} value: "{xpath}"')
        return self._wrap_proxy(el, By.XPATH, xpath)

    def get_items_by_xpath(self, xpath: str) -> List[WebElementProxy]:
        """
        находит все подходящие элементы таблицы по xpath (он должен быть относительно тэга таблицы)
        :param xpath:
        :return:
        """
        xpath = ''.join([self.value, xpath])
        try:
            elements = self._table.find_elements_by_xpath(xpath)
        except NoSuchElementException:
            raise TableElementNotFound(f'Elements not found by {By.XPATH} value: "{xpath}"')
        return [self._wrap_proxy(el, By.XPATH, xpath) for el in elements]

    def _wrap_proxy(self, element: WebElement, by, value) -> WebElementProxy:
        """
        Оборачивает инстанс WebElement, чтобы были доступны кастомные функции WebElementProxy
        :param element:
        :param by:
        :param value:
        :return:
        """
        return WebElementProxy(
            target_object=element,
            page=self._table.page,
            by=by,
            value=value,
        )
