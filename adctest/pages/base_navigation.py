from adctest.helpers.exceptions import BasePageException


class BaseNavigationMeta(type):
    """
    базовый метакласс, который реализует основную логику создания навигационных элементов из
    "сырых" классов
    """

    def __new__(mcs, class_name, bases, attrs):
        new_class = type.__new__(
            mcs, class_name, bases, attrs)

        return new_class


class BaseNavigation:
    page = None
    """ссылка на инстанс BasePage"""

    def __set_name__(self, owner, name):
        self.__navigation_name = name

    def _init_from_page(self, page):
        self.page = page

    def __getattr__(self, item):
        # вся магия происходит здесь
        # навигационный объект прокидывает все вызовы в связанную страницу,
        # если вызван атрибут, которого навигационный компонент не имеет
        if self.page:
            return getattr(self.page, item)
        raise BasePageException(f'{self.__class__.__name__} not initialized from Page object')
