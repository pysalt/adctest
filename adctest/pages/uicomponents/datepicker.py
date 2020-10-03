"""
Этот класс оборачивает инпут с дата-пикером (ngx-daterangepicker-material) и позволяет с ним взаимодействовать.
Внимание! Предполагается, что время устанавливается с учетом тайм-зоны
"""
from datetime import date, datetime
from typing import Callable

from adctest.helpers.exceptions import DatePickerNotFound, DatePickerException, DatePickerAttributeError
from adctest.pages import WebElementProxy
from adctest.pages.uicomponents.helpers.parsers import format_xpath_from_parent
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement


class AttributeDescriptor:
    value = None
    """значение xpath относительно datepicker, по которому искать элемент"""
    __attribute_name = None
    """имя атрибута базовой страницы, в котором хранится инстанс дескриптора"""

    def __init__(self, value=None):
        """
        :param value:
        """
        self.__attribute_name = None
        self.value = value
        self._validate_params()

    def _validate_params(self):
        if not self.value:
            raise DatePickerException('value param must be passed to AttributeDescriptor')

    def __set_name__(self, owner, name):
        self.__attribute_name = '_'.join([owner.__class__.__name__.lower(), name])

    def __get__(self, datepicker, objtype=None):
        if datepicker is None:
            return self
        datepicker.page.check_opened()

        return self._search_element(datepicker)

    def __getattribute__(self, item):
        if hasattr(AttributeDescriptor, item):
            return object.__getattribute__(self, item)
        raise AttributeError

    def _search_element(self, datepicker) -> WebElement:
        parent: WebElement = datepicker.component
        xpath = format_xpath_from_parent(self.value)
        try:
            return parent.find_element_by_xpath(xpath)
        except NoSuchElementException:
            raise DatePickerAttributeError(f'Attribute of datepicker not found by xpath: {xpath}')


class DatePicker:
    tag_name = 'ngx-daterangepicker-material'
    """имя тэга, внутри которого находится компонент"""
    body_class = 'md-drppicker'
    """Имя класса, по которому можно найти тело datepicker"""
    component: WebElement = None
    """
    хранится преобразованный в WebElement тэг и его содержимое:
    <ngx-daterangepicker-material>...</ngx-daterangepicker-material>
    """

    def __init__(self, element: WebElementProxy):
        parent_element = element.find_element_by_xpath('./..')
        self.component = self._find_component(parent_element)
        self.picker_panel = self._find_picker_panel(self.component)
        self._input = element

    def _find_component(self, parent_element: WebElement) -> WebElement:
        try:
            xpath = format_xpath_from_parent(self.tag_name)
            return parent_element.find_element_by_xpath(xpath)
        except NoSuchElementException:
            raise DatePickerNotFound(f'<{self.tag_name}> tag not found in parent tag of this element')

    def _find_picker_panel(self, component: WebElement) -> WebElement:
        try:
            return component.find_element_by_class_name(self.body_class)
        except NoSuchElementException:
            raise DatePickerNotFound(f'Cannot find datepicker body by class {self.body_class}')

    button_ok: WebElement = AttributeDescriptor('//button[contains(text(), "ok") or contains(text(), "OK")]')

    @property
    def is_visible(self):
        return self.picker_panel.is_displayed()

    def show(self):
        if not self.is_visible:
            self._input.click()

    @property
    def page(self):
        """
        Страница, на которой находится datepicker
        :return:
        """
        return self._input.page

    def _set_value(self, format_func: Callable, *func_args):
        self.show()
        value_to_set = format_func(*func_args)
        self._input.clear()
        self._input.send_keys(value_to_set)

    def set_time(self, from_time: datetime, to_time: datetime = None):
        """
        Устанавливает время в инпут дата-пикера, но не применяет его.
        Если передать оба аргумента, то установит период времени
        :param from_time:
        :param to_time:
        :return:
        """
        if to_time:
            self._set_value(self._format_time_range, from_time, to_time)
        else:
            self._set_value(self._format_time, from_time)

    def set_date(self, from_date: date, to_date: date = None):
        """
        Устанавливает дату в дата-пикер, но не применяет её.
        Если передать оба аргумента, то установит период дат
        :param from_date:
        :param to_date:
        :return:
        """
        if to_date:
            self._set_value(self._format_date_range, from_date, to_date)
        else:
            self._set_value(self._format_date, from_date)

    def set_date_and_apply(self, from_date: date, to_date: date = None):
        """
        Основной метод для использования. Открывает датапикер, устанавливает заданный период дат и нажимает
        кнопку ok
        :param from_date:
        :param to_date: Если None, то будет установлен не период, а дата, переданная в from_date
        :return:
        """
        self.set_date(from_date, to_date)
        self.button_ok.click()

    def set_time_and_apply(self, from_time: datetime, to_time: datetime = None):
        """
        Основной метод для использования. Открывает датапикер, устанавливает заданный период времени и нажимает
        кнопку ok
        :param from_time:
        :param to_time: Если None, то будет установлен не период, а время, переданное в from_time
        :return:
        """
        self.set_time(from_time, to_time)
        self.button_ok.click()

    def _format_date_range(self, from_: date, to_: date) -> str:
        return ' - '.join([self._format_date(from_), self._format_date(to_)])

    def _format_time_range(self, from_: datetime, to_: datetime) -> str:
        return ' - '.join([self._format_time(from_), self._format_time(to_)])

    @classmethod
    def _format_date(cls, date_to_format: date):
        return date_to_format.strftime('%m-%d-%Y')

    @classmethod
    def _format_time(cls, time_to_format: datetime):
        return time_to_format.strftime('%d/%m/%Y %H:%M')
