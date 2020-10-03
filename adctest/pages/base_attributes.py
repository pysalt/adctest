"""
В данном модуле при обращении к атрибутам объектов page можно использовать только методы и атрибуты,
описанные в AbstractBasePage
"""
from functools import wraps
from inspect import ismethod
from typing import Tuple, List, Set

from adctest.config import config
from adctest.helpers.exceptions import BasePageException
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException, NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

DATA_E2E_ATTRIBUTE_NAME = config.DATA_E2E_ATTRIBUTE


class WebElementProxyException(Exception):
    def __init__(self, msg=None, element=None):
        self.msg = msg
        self.element = element

    def __str__(self):
        exception_msg = "Message: %s\n" % self.msg
        if self.element is not None:
            exception_msg += "Occurred at element: %s" % self.element
        return exception_msg


class WebElementProxy(WebElement):
    """
    Данный класс проксирует доступ к инстансу WebElement, реализуя дополнительную логику,
    чтобы обеспечить ожидание загрузки ангулярного приложение и некоторых других фич
    """
    page = None
    """через этот атрибут можно получить доступ ко всем методам страницы BasePage, 
       атрибутом которой является данный элемент"""
    _obj: WebElement = None
    """здесь лежит инстанс класса WebElement, доступ к которым мы проксируем"""
    locator: Tuple[str, str] = None
    """текстовое представление для повторного поиска элемента (необходимо в некоторых методах WebElement)"""
    attr_name: str = None
    """имя атрибута в page, с которым связан этот объект (проставляется только, если объект получен через дескриптор)"""

    # noinspection PyMissingConstructor
    def __init__(self, page, by, value, target_object, attr_name=None):
        # пропускает __init__ метод класса WebElement, т.к. данный класс является проксирующим
        if isinstance(target_object, WebElementProxy):
            raise BasePageException('target_object already is instance WebElementProxy')
        object.__setattr__(self, 'page', page)
        object.__setattr__(self, '_obj', target_object)
        object.__setattr__(self, 'locator', (by, value))
        object.__setattr__(self, 'attr_name', attr_name)

    def __getattribute__(self, name: str):
        if proxy_has_attr(name):
            attr = object.__getattribute__(self, name)
        else:
            attr = getattr(self._obj, name)

        if ismethod(attr) and not name.startswith('__'):
            decorator = catch_not_attach_to_session(self)
            return decorator(attr)
        return attr

    def __setattr__(self, name, value):
        if proxy_has_attr(name):
            object.__setattr__(self, name, value)
            return
        setattr(self._obj, name, value)

    def __delattr__(self, name):
        if proxy_has_attr(name):
            object.__delattr__(self, name)
            return
        return delattr(self._obj, name)

    def until(self, condition, *args, **kwargs):
        self.page.wait.until(
            condition(self.locator, *args, **kwargs)
        )

    def until_not(self, condition, *args, **kwargs):
        self.page.wait.until_not(
            condition(self.locator, *args, **kwargs)
        )

    def click(self, focus_on_opened_tab: bool = True):
        """
        дождаться доступность элемента и кликнуть по нему (не ожидает после клика завершения чего-либо)
        :focus_on_opened_tab: Нужно ли фокусироваться на новой вкладке, если она будет открыта
        :return:
        """
        self.until(EC.element_to_be_clickable)
        self._obj.click()
        if focus_on_opened_tab:
            self.page.focus_on_last_opened_tab()

    def click_and_wait(self, focus_on_opened_tab: bool = True):
        """
        выполняет стандартный клик по элементу, но после клика ждет завершения запущенного действия.
        Сигнал завершения - отсутствие лоадеров станицы и таблицы
        :focus_on_opened_tab: Нужно ли фокусироваться на новой вкладке, если она будет открыта
        :return:
        """
        self.click(focus_on_opened_tab=focus_on_opened_tab)
        self.page.wait_loaders_hidden()

    @property
    def page_wait(self):
        """
        реализует доступ к wait объекту страницу, если нужно реализовать ожидание чего-либо
        :return:
        """
        return self.page.wait

    def _reload_target_object(self) -> None:
        """
        Перегружает оригинальный WebElement. Нужно, т.к. элементы даже на неперезагруженной странице
        могут быть удалены из сессии селениума (происходит это потому, что почти на любом действии
        ангуляр удаляет и добавляет элементы DOM)
        :return:
        """
        if self.attr_name and self.attr_name in self.page._cached_attrs:
            self.page._cached_attrs.pop(self.attr_name, None)
        obj = self.page._find_element(*self.locator)

        object.__setattr__(self, '_obj', obj)
        # добавляем обратно элемент в кэш страницы, чтобы при следующем обращении через дескриптор не искать снова
        if self.attr_name:
            self.page._cached_attrs[self.attr_name] = self


def get_subclass_attributes() -> Set[str]:
    """
    Небольшой хэлпер, который возвращает имена атрибутов только прокси-класса WebElementProxy
    :return:
    """
    if hasattr(get_subclass_attributes, '__cached_attrs'):
        return get_subclass_attributes.__cached_attrs

    bases = WebElementProxy.__bases__
    if len(bases) > 1:
        raise NotImplemented('It works only with one parent classes')
    attrs = set(WebElementProxy.__dict__.keys())
    setattr(get_subclass_attributes, '__cached_attrs', attrs)
    return attrs


def proxy_has_attr(name: str) -> bool:
    """
    Аналог hasattrs для WebElementProxy, реализовано вне класса, чтобы не зацикливаться
    в методе __getattribute__
    :param name:
    :return:
    """
    if name in get_subclass_attributes():
        return True
    return False


def catch_not_attach_to_session(current_obj: WebElementProxy):
    """
    декоратор, позволяющий перегрузить инстанс WebElement, если он пропал из сессии брузера.
    инстанс WebElement хранится в прокси-объекте WebElementProxy, таким образом мы перегружаем
    только объект селениума, при этом инстанс WebElementProxy остается тот же, что позволяет
    не пересоздавать заново объекты BasePage
    :param current_obj:
    :return:
    """
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except StaleElementReferenceException:
                current_obj._reload_target_object()
                return function(*args, **kwargs)
            except NoSuchElementException:
                raise
            except WebDriverException as ex:
                raise WebElementProxyException(str(ex), current_obj.attr_name or 'Object didnt attach to Page')

        return wrapper

    return decorator


class ElementDescriptor:
    """
    Дексриптор для WebElementProxy. Позволяет реализовать ленивую загрузку WebElement,
    т.е. объект селениума создается только в момент обращение к атрибуту класса через этот дескриптор
    """
    search_by = None
    """тип поиска элемента (по xpath, class и т.д.)"""
    value = None
    """значение, по которому искать элемент"""
    many = None
    """будет ли найдено несколько элементов на странице по данному паттерну"""
    __element_name = None
    """имя атрибута базовой страницы, в котором хранится инстанс дескриптора"""

    def __init__(self, search_by=None,
                 value=None,
                 many=False):
        """
        Единственный доступный метод, в который надо передать параметры для поиска веб-элемента на странице
        :param search_by: тип локатора (по умолчанию xpath)
        :param value: значение локатора
        :param many: флаг, что по переданному локатору будет найдено несколько элементов
        """
        self.__element_name = None
        self.search_by = search_by
        self.value = value
        self.many = many
        if self.value and not self.search_by:
            self.search_by = By.XPATH
        self._validate_params()

    def _validate_params(self):
        if not self.search_by or not self.value:
            raise BasePageException('[value, search_by] param must be passed to ElementDescriptor')

    def __set_name__(self, owner, name):
        self.__element_name = name

    def __get__(self, page, objtype=None):
        if page is None:
            return self
        page.check_opened()

        cached_attrs = page._cached_attrs
        if cached_attrs.get(self.__element_name) is None:
            cached_attrs[self.__element_name] = self._search_element(page)
        return cached_attrs[self.__element_name]

    def __getattribute__(self, item):
        if hasattr(ElementDescriptor, item):
            return object.__getattribute__(self, item)
        raise AttributeError

    def _search_element(self, page):
        if self.many:
            elements = page._find_elements(self.search_by, self.value)
            proxy_elements = []
            for item in elements:
                proxy_elements.append(
                    WebElementProxy(
                        target_object=item,
                        page=page,
                        by=self.search_by,
                        value=self.value,
                        attr_name=self.__element_name,
                    )
                )
            return proxy_elements

        web_element = page._find_element(self.search_by, self.value)
        return WebElementProxy(
            target_object=web_element,
            page=page,
            by=self.search_by,
            value=self.value,
            attr_name=self.__element_name,
        )


class ListOfElementDescriptor:
    """
    Класс-дескриптор, подобный ElementDescriptor, но он позволяет описать группу элементов,
    которые различаются индексами.
    <button name="row_1"></button>
    <button name="row_2"></button>
    Для того, чтобы не множить описание таких элементов в базовой странице и нужен этот класс.
    Он позволяет описать элементы выше так:
    elements = ListOfElementDescriptor(base_name_parts=['row_'])
    и тогда любой элемент будет доступен так:
    elements.get(1)
    elements.get(2)
    """
    base_name_parts: list = None
    """список из общих частей значения атрибута, объединяемых элемнтов"""
    tag_attr_name: str = None
    """имя атрибута, по значению которого группируются элементы"""
    many: bool = None
    """Флаг, что по полному имени будет найдено несколько элементов"""
    page = None
    # пока поддерживает поиск только по xpath
    search_by: str = 'xpath'

    def __init__(self, base_name_parts: List[str], many: bool = False, tag_attr_name: str = DATA_E2E_ATTRIBUTE_NAME,
                 context=None):
        """

        :param base_name_parts: список из общих частей значения атрибута, объединяемых элемнтов
        :param many: флаг, что по полному значению атрибута будет найдено несколько элементов
        :param tag_attr_name: имя атрибута, по значению которого группируются элементы
        :param context:
        """
        if not isinstance(base_name_parts, list):
            raise BasePageException('base_name_parts must be list of string')
        self.base_name_parts = [name.strip('_') for name in base_name_parts]
        self.many = many
        self.tag_attr_name = tag_attr_name
        self.page = context

    def get_by_index(self, *numbers) -> WebElementProxy:
        """
        Получить элемент по его порядковому номеру на отрисованной странице. Является интерфейсом к
        get-методу, который ограничивает numbers только типом int
        :param numbers:
        :return:
        """
        if not all([isinstance(num, int) for num in numbers]):
            raise BasePageException('all of parameters must be int')
        return self.get(*numbers)

    def get_no_load(self, *numbers) -> ElementDescriptor:
        """
        Возвращает дескриптор элемента.
        Основное применение: ожидание появления элемента на странице
        Для этого дескриптор необходимо передать в метод страницы wait_accessibility_of()
        :return:
        """
        attr_name = self._make_attr_name(numbers)
        return self._get_attribute_descriptor(attr_name)

    def get(self, *numbers) -> WebElementProxy:
        """
        Заполнить параметрами numbers шаблон base_name_parts и вернуть подходящий элемент, если он есть
        :param numbers: список динамических параметров, которые надо объединить с base_name_parts
        :return:
        """
        attr_name = self._make_attr_name(numbers)
        descriptor = self._get_attribute_descriptor(attr_name)
        return descriptor.__get__(self.page)

    def _get_attribute_descriptor(self, attr_name: str) -> ElementDescriptor:
        if attr_name not in self.page.__dict__:
            descriptor = self._construct_attribute_descriptor(attr_name)
            setattr(self.page, attr_name, descriptor)
        return getattr(self.page, attr_name)

    def _construct_attribute_descriptor(self, attr_name: str) -> ElementDescriptor:
        value = self._print_search_value(attr_name)
        descriptor = ElementDescriptor(search_by=self.search_by, value=value, many=self.many)
        descriptor.__set_name__(None, attr_name)
        return descriptor

    def _print_search_value(self, attr_name: str) -> str:
        return f'//*[@{self.tag_attr_name}="{attr_name}"]'

    def _make_attr_name(self, args):
        params = list(map(str, args))
        if len(params) != len(self.base_name_parts):
            raise BasePageException(f'You pass to get method only {len(params)} params '
                                    f'but required {len(self.base_name_parts)}')

        indexed_names = []
        for val in zip(self.base_name_parts, params):
            indexed_names.append('_'.join(val))

        return '_'.join(indexed_names)

    def __get__(self, page, objtype=None):
        self.page = page
        return self

    def __getitem__(self, item: int):
        if not isinstance(item, int):
            raise BasePageException('ListOfElementDescriptor support only number access to attributes')
        return self.get(item)
