from enum import Enum
from typing import Optional, Union

from adctest.pages import WebElementProxy
from lxml.html import HtmlElement

from adctest.helpers.exceptions import NoSuchElementError
from adctest.pages.uicomponents.helpers.parsers import get_html_from_string
from selenium.webdriver.remote.webelement import WebElement


class _ToastTypes(Enum):
    error = 'toast-error'
    info = 'toast-info'
    success = 'toast-success'
    warning = 'toast-warning'


class Toast:
    """
    Этот класс кэширует html-представление "всплывшего" уведомления, открывает доступ к его основным компонентам:
    заголовок, основной текст, тип уведомления (успех, ошибка, инфо и т.д.), но не позволяет взаимодействовать с ним
    на странице, т.к. он пропадает и остается такая структура:
    <toaster-container>
        <div id="toast-container"><!----></div>
    </toaster-container>

    Вызовет ошибку NoSuchElementError, если будет передан объект, связанный с уже закрывшимся уведомлением
    """
    component_id = 'toast-container'
    _component_class = 'toast'
    _title_class = 'toast-title'
    _message_class = 'toast-message'

    component: HtmlElement = None
    """
    хранится преобразованный в HtmlElement тэг и его содержимое:
    <div toastcomp="" class="toast"><div/>
    """

    Types = _ToastTypes

    def __init__(self, element: Union[WebElement, WebElementProxy]):
        self._element = element
        self._outer_html: HtmlElement = get_html_from_string(element.get_attribute('outerHTML'))
        if self.component_id != element.get_attribute('id'):
            raise NoSuchElementError(f'Toast element container must have id="{self.component_id}".')

        self.component = self._get_base_element()
        self._type = self._get_type()

    def _get_base_element(self):
        component = self._outer_html.find_class(self._component_class)
        if not component:
            raise NoSuchElementError(f'Toast element disappeared from the page when the object was created')
        return component[0]

    def _get_type(self):
        for t in self.Types:
            if t.value in self.component.classes:
                return t
        return None

    def hide(self):
        """
        Скрывает уведомление, кликая по нему
        :return:
        """
        if self._element.is_displayed():
            self._element.click()

    @property
    def type(self):
        """
        Тип уведомления
        :return:
        """
        return self._type

    @property
    def is_success(self):
        """
        Проверить, что уведомление типа success
        :return:
        """
        return self.type and self.type is self.Types.success

    @property
    def message(self):
        """
        Основной текст уведомления
        :return:
        """
        return self._get_element_text(self._message_class)

    @property
    def title(self):
        """
        Текст заголовка уведомления
        :return:
        """
        return self._get_element_text(self._title_class)

    def _get_element_text(self, css_class: str) -> Optional[str]:
        tag: Optional[HtmlElement] = self.component.find_class(css_class)
        if tag:
            return str(tag[0].text_content())

    @property
    def is_error(self):
        """
        Проверить, что уведомление типа error
        :return:
        """
        return self.type and self.type is self.Types.error
