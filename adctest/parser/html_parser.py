import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from adctest.config import config
from adctest.parser.const import (
    PAGE_PATH_NAME,
    NAV_PAGE_PATH_NAME,
    RAW_PAGE_CLASS_POSTFIX,
    RAW_PAGE_PATH_NAME,
)
from adctest.parser.exceptions import ParserException
from adctest.pages import PageConfig, BasePage, BasePageMeta, BaseNavigation, BaseNavigationMeta, ElementDescriptor, \
    WebElementProxy
from adctest.parser.utils import Utils, RelativeImportPath, LineRange
from lxml.etree import XMLSyntaxError
from selenium.webdriver.common.by import By

from lxml.html import HtmlElement

logger = logging.getLogger('e2e-test')


EMPTY_CLASS_BODY = '    pass\n'

PAGE_CLASS_REPR = """\
\"""
Этот класс наследуется от автогенерируемого, его можно редактировать
\"""
# put new imports here
{additional_imports}


class {page_class}({raw_page_class}, metaclass={base_metaclass}):
"""

RAW_NAV_CLASS_REPR = """\
\"""
Это автогенерируемый класс, его нельзя редактировать
\"""
# put new imports from non project libraries here
from typing import List
{additional_imports}


class {raw_page_class}({base_page_class}):
"""

RAW_PAGE_CLASS_REPR = """\
\"""
Это автогенерируемый класс, его нельзя редактировать
\"""
# put new imports from non project libraries here
from typing import List
from adctest.pages import PageConfig
{additional_imports}


class {raw_page_class}({base_page_class}):
    page_url = '{page_url}'
    page_conf: PageConfig = '{page_conf_name}'
"""

ATTRIBUTE_REPR = """\
    {attribute_name}: {attribute_annotation} = {attribute_value}
    \"""{path_to_attribute}\"""
"""
NAV_CLASS_OBJ_REPR = """\
    {attr_name}: {class_name} = {class_name}()
"""

XPATH_BY_CSS = r"""'//*[contains(@class, "{class_name}")]'"""
XPATH_BY_TAG_ATTR = r"""'//*[@{attr_name}="{attr_value}"]'"""


class PageHelper:
    """
    такая реализация пока нет датаклассов
    """
    html_obj: HtmlElement = None
    """объект, содержащий дерево текущей страницы"""

    py_page_file_name: str = None
    """имя модуля, в который будет записан класс, описывающий текущую страницу"""
    path_to_write_raw_page: Path = None
    """полный путь для записи "сырого" класса"""
    path_to_write_page: Path = None
    """полный путь для записи основного класса страницы"""

    class_name: str = None
    """имя основного класса страницы"""
    raw_class_name: str = None
    """имя "сырого" класса страницы"""
    attributes: List[str] = []
    """атрибуты сырого класса, которые были найдены на исходной странице (уже преобразованы в py-строки)"""
    base_page_import_path: str = None
    """путь относительного импорта BasePage в модуль "сырого" класса"""
    base_meta_page_import_path: str = None
    """путь относительного импорта BasePageMeta в модуль базового класса"""
    raw_page_import_path: str = None
    """путь относительного импорта "сырого" класса в модуль базового класса"""
    element_descriptor_and_proxy_import_path: str = None
    """путь относительного импорта WebElementProxy и ElementDescriptor классов в модуль "сырого" класса"""


class AngularFormatParser:
    """
    базовый класс-парсер. Для реализации парсера для нового ангуляр приложения необходимо
    наследоваться от него.
    Для каждой страницы ангуляр-приложения он генерит два файла:
    e2e--pages--<имя_страницы>
       |-raw_pages--<имя_страницы>

    в pages кладется GeneratedClass - базовый класс, который импортируется для тестов
    в raw_pages кладется GeneratedClassRaw - "сырой" класс, который наполняется автогенерируемыми атрибутами
    Для этих классов реализуется следующая структура наследования:
    BasePage->GeneratedClassRaw->GeneratedClass(metaclass=BasePageMeta)

    GeneratedClassRaw наполняется атрибутами, которые являются прокси-объектами WebElementProxy,
    полученными через дескриптор ElementDescriptor
    """

    app_name: str = None
    """имя ангулярного приложения (имя поддиректории в js), устанавливается в классе наследнике"""

    root_path: Path = None
    """относительный путь до корня js-приложения, устанавливается в классах наследниках"""
    backend_path: Path = None
    """абсолютный путь до /backend, генерится в рантайме"""
    project_path: Path = None
    """абсолютный путь до root_path, генерится в рантайме"""
    relative_e2e_path: Path = Path('py/tests/hasoffers/e2e/')
    """относительный путь до e2e папки"""
    e2e_path: Path = None
    """абсолютный путь до e2e папки, генерится в рантайме"""
    pages_path: Path = None
    """абсолютный путь до папки со страницами-шаблонами, которые можно менять, генерится в рантайме"""
    raw_pages_path: Path = None
    """абсолютный путь до папки c автогенирируемыми страницами, генерится в рантайме"""

    base_attrs_search_patterns = ['name', config.DATA_E2E_ATTRIBUTE, ]

    components_relative_path: Path = None
    """путь относительно root_path до папки со страницами"""
    head_relative_path: Path = None
    """путь относительно root_path до файла с версткой head страниц"""
    side_nav_relative_path: Path = None
    """путь относительно root_path до файла с версткой бокового меню"""
    footer_relative_path: Path = None
    """путь относительно root_path до файла с версткой нижней части страницы"""
    navigation_classes_import_list: List[Tuple[str, Path]] = []
    """классы и полные пути общих для всех страниц классов навигации"""

    @classmethod
    def _set_project_paths(cls) -> None:
        if not cls.root_path:
            raise NotImplementedError('root_path attr must be set to subclass')

        cls.backend_path = Utils.get_full_path_to_backend()
        cls.e2e_path = cls.backend_path.joinpath(cls.relative_e2e_path)
        cls.project_path = cls.backend_path.joinpath(cls.root_path)

    @classmethod
    def _set_pages_paths(cls) -> None:
        if not cls.app_name:
            raise NotImplementedError('app_name attr must be set to subclass')

        cls.pages_path = cls.e2e_path.joinpath(PAGE_PATH_NAME, cls.app_name)
        Utils.create_module_dir(module_path=cls.pages_path)
        cls.raw_pages_path = cls.e2e_path.joinpath(RAW_PAGE_PATH_NAME, cls.app_name)
        Utils.create_module_dir(module_path=cls.raw_pages_path)

    @classmethod
    def parse(cls) -> None:
        """
        Вызов метода выполняет все необходимые действия по парсингу.
        в классе-наследнике необходимо реализовать методы create_navigation_components и custom_parse
        :return:
        """
        cls._set_project_paths()
        cls._set_pages_paths()
        cls.create_navigation_components()
        cls.custom_parse()

    @classmethod
    def get_path_to_store(cls) -> Path:
        """
        Must return absolute path to pages store folder
        :return:
        """
        raise NotImplementedError('method get_path_to_store must be implemented')

    @classmethod
    def create_navigation_components(cls) -> None:
        """
        Создает базовые компоненты, присутствующие на любой странице (панель навигации и т.д.).
        Необходимо реализовать в сабкласе. Внутри производить вызовы create_footer,
        create_side_nav, create_head с необходимыми для конкретного приложения параметрами
        :return:
        """
        raise NotImplementedError('method create_navigation_components must be implemented')

    @classmethod
    def custom_parse(cls) -> None:
        """
        в данном методе необходимо реализовать свою логику парсинга основных страниц проекта,
        т.к. в каждом приложении js логика размещения отличается.
        Внутри производить вызовы высокоуровневых функций parse_pages или create_page
        с необходимыми для конкретного приложения параметрами
        :return:
        """
        raise NotImplementedError('method custom_parse() must be implemented')

    @classmethod
    def create_footer(cls) -> None:
        """
        Создает класс, описывающий футер страницы.
        Вызывать в create_navigation_components с необходимыми параметрами
        :return:
        """
        if cls.footer_relative_path:
            path = cls.project_path.joinpath(cls.footer_relative_path)
            cls._create_navigation(path)

    @classmethod
    def create_side_nav(cls, css_patterns: Optional[List[str]] = None, patterns_by_attr: Optional[List[str]] = None,
                        file_name_prefix: Optional[str] = None, search_range: Optional[LineRange] = None,
                        raw_page_custom_attr: Optional[List[str]] = None) -> None:
        """
        Создает класс, описывающий левую навигационную панель.
        Вызывать в create_navigation_components с необходимыми параметрами
        :param css_patterns: список из css-классов по которым искать кастомный элемент
        :param patterns_by_attr: список из имен атрибутов по которым искать кастомный элемент
        :param file_name_prefix: префикс к автогенерируему имени файла, куда будет сохранен класс навигации
        :param search_range: объект LineRange, если в файле нужно искать элементы в определенном промежутке строк
        :param raw_page_custom_attr: уже подготовленные для записи кастомные атрибуты (если элемент нельзя
        было найти по паттернам css/attributes и нужно реализовать свой)
        :return:
        """
        if cls.side_nav_relative_path:
            path = cls.project_path.joinpath(cls.side_nav_relative_path)
            cls._create_navigation(path, custom_css_patterns=css_patterns, custom_patterns_by_attr=patterns_by_attr,
                                   file_name_prefix=file_name_prefix, search_range=search_range,
                                   raw_page_custom_attr=raw_page_custom_attr, )

    @classmethod
    def create_head(cls, file_name_prefix: Optional[str] = None, search_range: Optional[LineRange] = None,
                    raw_page_custom_attr: Optional[List[str]] = None) -> None:
        """
        Создает класс, описывающий хедер страницы.
        Вызывать в create_navigation_components с необходимыми параметрами
        :param file_name_prefix: префикс к автогенерируему имени файла, куда будет сохранен класс навигации
        :param search_range: объект LineRange, если в файле нужно искать элементы в определенном промежутке строк
        :param raw_page_custom_attr: уже подготовленные для записи кастомные атрибуты (если элемент нельзя
        было найти по паттернам css/attributes и нужно реализовать свой)
        :return:
        """
        if cls.head_relative_path:
            path = cls.project_path.joinpath(cls.head_relative_path)
            cls._create_navigation(path, file_name_prefix=file_name_prefix, search_range=search_range,
                                   raw_page_custom_attr=raw_page_custom_attr, )

    @classmethod
    def parse_pages(cls, pages_routes: Dict[str, str]) -> None:
        """
        Позволяет распарсить все html-страницы, лежащие в директории components_relative_path и её поддиректориях
        :param pages_routes: дикт вида {<относительный_путь_до_страницы>: <относительный_url_страницы>}
        :return:
        """
        components_path: Path = cls.project_path.joinpath(cls.components_relative_path)
        added_names = set()

        for path in components_path.iterdir():
            if path.is_dir():
                html_paths = list(path.rglob('*.html'))
                names = [p.stem for p in html_paths]
                has_same_names = len(names) != len(set(names))
                for p in html_paths:
                    name_prefix = ''
                    if p.parent != path and has_same_names:
                        name_prefix = p.relative_to(path).parent.name.split('-')[-1]
                    cls.create_page(p, page_url=pages_routes.get(p.stem, ''), file_name_prefix=name_prefix)
                    added_names.add(p.name)

    @classmethod
    def create_page(cls, path_to_html: Path, custom_css_patterns: Optional[List[str]] = None,
                    custom_patterns_by_attr: Optional[List[str]] = None, page_url: str = "",
                    file_name_prefix: Optional[str] = None, search_range: Optional[LineRange] = None) -> None:
        """
        Используется в parse_pages(), но может быть вызвана отдельно, если необходимо распарсить дополнительные
        страницы, которые находятся в директории, отличной от указанной в components_relative_path
        :param path_to_html: абсолютный путь до файла-исходника
        :param custom_css_patterns: список из css-классов по которым искать кастомный элемент
        :param custom_patterns_by_attr: список из имен атрибутов по которым искать кастомный элемент
        :param page_url: относительный url (без домена), чтобы открыть данную страницу в браузере
        :param file_name_prefix: префикс к автогенерируему имени файла, куда будет сохранен класс навигации
        :param search_range: объект LineRange, если в файле нужно искать элементы в определенном промежутке строк
        :return:
        """
        try:
            obj: PageHelper = cls._parse_html(path_to_html, custom_css_patterns, custom_patterns_by_attr,
                                              file_name_prefix=file_name_prefix, search_range=search_range, )
        except XMLSyntaxError:
            logger.warning('File %s is empty or have invalid syntax. Skip parsing', path_to_html)
            return

        additional_imports = [
            obj.base_page_import_path,
        ]
        if obj.attributes:
            additional_imports.append(obj.element_descriptor_and_proxy_import_path)

        page_raw = RAW_PAGE_CLASS_REPR.format(
            raw_page_class=obj.raw_class_name,
            additional_imports='\n'.join(additional_imports),
            base_page_class=BasePage.__name__,
            page_url=page_url,
            app_name=cls.app_name,
            base_metaclass=BasePageMeta.__name__,
        )

        page_attrs, page_imports = cls._get_navigations_for_page(path_to_write_page=obj.path_to_write_page)
        page_imports.extend([obj.base_meta_page_import_path, obj.raw_page_import_path])

        page = PAGE_CLASS_REPR.format(
            page_class=obj.class_name,
            raw_page_class=obj.raw_class_name,
            base_metaclass=BasePageMeta.__name__,
            additional_imports='\n'.join(page_imports),
        )

        cls._create_page_file(obj.path_to_write_raw_page, page_raw, obj.attributes, rewrite=True)
        cls._create_page_file(obj.path_to_write_page, page, page_attrs or [EMPTY_CLASS_BODY])

        cls._add_page_class_to_init_file(obj.path_to_write_page, obj.class_name)

    @classmethod
    def _parse_html(cls, path_to_html: Path, custom_css_patterns: Optional[List[str]] = None,
                    custom_patterns_by_attr: Optional[List[str]] = None,
                    is_nav_component: bool = False, file_name_prefix: str = '',
                    search_range: Optional[LineRange] = None) -> PageHelper:
        """
        Основной метод, который парсит html-страницы. Собирает общие для всех страниц данные
        и возвращает объект PageHelper. Не вызывать напрямую.
        :param path_to_html:
        :param custom_css_patterns:
        :param custom_patterns_by_attr:
        :param is_nav_component:
        :param file_name_prefix: префикс к имени создаваемого файла модуля
        :param search_range: интервал в строках файла для поиска (если нужен не весь файл)
        :return:
        """
        obj: PageHelper = PageHelper()
        obj.html_obj = Utils.get_html_from_file(path=path_to_html)
        file_name = Path('_'.join(filter(lambda o: o, [file_name_prefix, path_to_html.name])))

        obj.class_name = Utils.get_class_name_from_file_name(file_name)
        obj.raw_class_name = f'{obj.class_name}{RAW_PAGE_CLASS_POSTFIX}'

        obj.py_page_file_name = Utils.get_python_format_file_name(file_name)
        obj.path_to_write_page = cls._get_path_to_write(cls.pages_path, obj.py_page_file_name, is_nav_component)
        obj.path_to_write_raw_page = cls._get_path_to_write(cls.raw_pages_path, obj.py_page_file_name, is_nav_component)

        obj.attributes = cls._search_named_tags(page=obj.html_obj, path_to_html=path_to_html,
                                                custom_css_patterns=custom_css_patterns,
                                                custom_patterns_by_attr=custom_patterns_by_attr,
                                                search_range=search_range,
                                                )

        func = Utils.get_module_path_by_class
        base_class_path = func(BaseNavigation) if is_nav_component else func(BasePage)
        base_class_name = BaseNavigation.__name__ if is_nav_component else BasePage.__name__
        base_metaclass_path = func(BaseNavigationMeta) if is_nav_component else func(BasePageMeta)
        base_metaclass_name = BaseNavigationMeta.__name__ if is_nav_component else BasePageMeta.__name__
        element_descriptor_and_proxy_class_path = func(ElementDescriptor)
        element_descriptor_class_name = ElementDescriptor.__name__
        element_proxy_class_name = WebElementProxy.__name__

        obj.base_page_import_path = RelativeImportPath.get(
            root=cls.e2e_path,
            to_path=obj.path_to_write_raw_page,
            from_path=base_class_path,
            class_names=[base_class_name],
        )

        obj.base_meta_page_import_path = RelativeImportPath.get(
            root=cls.e2e_path,
            to_path=obj.path_to_write_page,
            from_path=base_metaclass_path,
            class_names=[base_metaclass_name],
        )

        obj.element_descriptor_and_proxy_import_path = RelativeImportPath.get(
            root=cls.e2e_path,
            to_path=obj.path_to_write_raw_page,
            from_path=element_descriptor_and_proxy_class_path,
            class_names=[element_descriptor_class_name, element_proxy_class_name],
        )

        obj.raw_page_import_path = RelativeImportPath.get(
            root=cls.e2e_path,
            to_path=obj.path_to_write_page,
            from_path=obj.path_to_write_raw_page,
            class_names=[obj.raw_class_name],
        )

        return obj

    @classmethod
    def _get_path_to_write(cls, pages_root: Path, file_name: Path, is_nav_component: bool) -> Path:
        if is_nav_component:
            pages_root = pages_root.joinpath(NAV_PAGE_PATH_NAME)
            Utils.create_module_dir(pages_root)
        return pages_root.joinpath(file_name)

    @classmethod
    def _create_navigation(cls, path_to_html: Path, custom_css_patterns: Optional[List[str]] = None,
                           custom_patterns_by_attr: Optional[List[str]] = None,
                           file_name_prefix: Optional[str] = None, search_range: Optional[LineRange] = None,
                           raw_page_custom_attr: Optional[List[str]] = None) -> None:
        """
        Создает классы для навигационных частей страницы
        :param path_to_html:
        :param custom_css_patterns:
        :param custom_patterns_by_attr:
        :param file_name_prefix:
        :param search_range:
        :param raw_page_custom_attr:
        :return:
        """
        obj: PageHelper = cls._parse_html(path_to_html, custom_css_patterns, custom_patterns_by_attr,
                                          is_nav_component=True, file_name_prefix=file_name_prefix,
                                          search_range=search_range, )

        additional_imports = [
            obj.base_page_import_path,
        ]
        if obj.attributes or raw_page_custom_attr:
            additional_imports.append(obj.element_descriptor_and_proxy_import_path)

        page_raw = RAW_NAV_CLASS_REPR.format(
            raw_page_class=obj.raw_class_name,
            additional_imports='\n'.join(additional_imports),
            base_page_class=BaseNavigation.__name__,
        )

        page = PAGE_CLASS_REPR.format(
            page_class=obj.class_name,
            raw_page_class=obj.raw_class_name,
            additional_imports='\n'.join([obj.base_meta_page_import_path, obj.raw_page_import_path]),
            base_metaclass=BaseNavigationMeta.__name__,
        )

        if raw_page_custom_attr:
            obj.attributes.extend(raw_page_custom_attr)

        cls._create_page_file(obj.path_to_write_raw_page, page_raw, obj.attributes or [EMPTY_CLASS_BODY], rewrite=True)
        cls._create_page_file(obj.path_to_write_page, page, [EMPTY_CLASS_BODY])

        init_file_path: Path = cls._add_page_class_to_init_file(obj.path_to_write_page, obj.class_name)
        cls.navigation_classes_import_list.append((obj.class_name, init_file_path))

    @classmethod
    def _get_navigations_for_page(cls, path_to_write_page: Path) -> Tuple[List[str], List[str]]:
        """
        Формирует из классов навигации атрибуты навигации для каждой базовой страницы
        :param path_to_write_page: пбсолютный путь до модуля в который нужен импорт
        :return:
        """
        attrs = []
        classes_imports = []
        for class_name, full_path in cls.navigation_classes_import_list:
            attr = NAV_CLASS_OBJ_REPR.format(class_name=class_name, attr_name=class_name.lower())
            attrs.append(attr)
            class_import = RelativeImportPath.get(
                root=cls.e2e_path,
                to_path=path_to_write_page,
                from_path=full_path,
                class_names=[class_name]
            )
            classes_imports.append(class_import)

        return attrs, classes_imports

    @classmethod
    def _create_page_file(cls, path: Path, page_header: str, page_attrs: List[str],
                          rewrite: bool = False) -> None:
        """
        Записывает сгенеренные классы в файлы
        :param path: абсолютный путь файла, в который записывать
        :param page_header: преобразованный в строку заголовок класса и импорты
        :param page_attrs: преобразованные в строку атрибуты класса
        :param rewrite: флаг, обозначающий перезаписывать ли файл
        :return:
        """
        if not rewrite and path.exists():
            logger.info('Path "%s" is already exists. It will not be rewritten', path)
            return

        with path.open('w') as f:
            f.write(page_header)
            if page_attrs:
                for attr in page_attrs:
                    f.write(attr)

    @classmethod
    def _add_page_class_to_init_file(cls, from_path: Path, class_name: str) -> Path:
        """
        добавляет импорт нового класса в init файл
        :param from_path:
        :param class_name:
        :return:
        """
        init_path: Path = from_path.parent.joinpath('__init__.py')
        import_path: str = RelativeImportPath.get(
            root=cls.e2e_path,
            to_path=init_path,
            from_path=from_path,
            class_names=[class_name]
        )

        with init_path.open('r') as f:
            data = f.read()
            if import_path in data:
                return init_path
        with init_path.open('a') as f:
            f.write(f'{import_path}\n')
        return init_path

    @classmethod
    def _search_named_tags(cls, page: HtmlElement, path_to_html: Path, custom_css_patterns: List[str] = None,
                           custom_patterns_by_attr: List[str] = None,
                           search_range: Optional[LineRange] = None) -> List[str]:
        """
        Основная функция реализующая поиск атрибутов класса
        :param page: объект html
        :param path_to_html: абсолютный путь до файла html
        :param custom_css_patterns: список из css-классов по которым искать кастомный элемент
        :param custom_patterns_by_attr: список из имен атрибутов по которым искать кастомный элемент
        :param search_range: объект LineRange, если в файле нужно искать элементы в определенном промежутке строк
        :return:
        """
        attrs = []
        patterns_by_attr = deepcopy(cls.base_attrs_search_patterns)
        if custom_patterns_by_attr:
            patterns_by_attr.extend(custom_patterns_by_attr)

        if custom_css_patterns:
            attrs.extend(cls._search_by_css_patterns(page, path_to_html, custom_css_patterns, search_range))
        if patterns_by_attr:
            attrs.extend(cls._search_by_tag_attr_patterns(page, path_to_html, patterns_by_attr, search_range))

        return attrs

    @classmethod
    def _search_by_css_patterns(cls, page: HtmlElement, path_to_html: Path, custom_css_patterns: List[str],
                                search_range: Optional[LineRange] = None) -> List[str]:
        """
        Функция реализующая поиск атрибутов по css-классу
        :param page:
        :param path_to_html:
        :param custom_css_patterns:
        :param search_range:
        :return: найденный атрибут, форматированный для записи в py-файл
        """
        res = []
        for pattern in custom_css_patterns:
            el = page.find_class(pattern)
            if not el:
                logger.warning('Element not found by custom css pattern <%s>', pattern)
                continue
            if len(el) > 1:
                raise ParserException('By custom css pattern <%s> found more then one elements: %s',
                                      pattern, el)
            if search_range and el.sourceline not in search_range:
                logger.warning('Element found by custom css pattern <%s> not in search %s', pattern, search_range)
                continue
            res.append(cls._format_element_by_css(path_to_html=path_to_html, element=el[0], css_class=pattern))
        return res

    @classmethod
    def _format_element_by_css(cls, path_to_html: Path, element: HtmlElement, css_class: str) -> str:
        """
        форматирует найденный элемент html по css-паттерну в атрибут генерируемого класса python
        :param path_to_html:
        :param element:
        :param css_class:
        :return:
        """
        xpath = XPATH_BY_CSS.format(class_name=css_class)
        attribute_value = cls._format_attribute_value(xpath=xpath, many=False)
        return cls._print_element_in_py_repr(element, css_class, attribute_value, path_to_html, many=False)

    @classmethod
    def _search_by_tag_attr_patterns(cls, page: HtmlElement, path_to_html: Path, custom_patterns_by_attr: List[str],
                                     search_range: Optional[LineRange] = None) -> List[str]:
        """
        Функция реализующая поиск атрибутов по их атрибутам
        :param page:
        :param path_to_html:
        :param custom_patterns_by_attr:
        :param search_range:
        :return: найденный атрибут, форматированный для записи в py-файл
        """
        res = []
        for attr_name in custom_patterns_by_attr:
            prepared_name = attr_name.lower()
            search_mask = f'//*[@{prepared_name}]'
            elements: List[HtmlElement] = page.xpath(search_mask)
            if elements:
                added_elements: Dict[str, List] = {}
                for el in elements:
                    if search_range and el.sourceline not in search_range:
                        continue
                    attr_value = el.attrib[prepared_name]
                    if '{{' in attr_value:
                        # пропускаем элементы у которых атрибут формируется во время выполнения
                        continue
                    if attr_value in added_elements:
                        added_elements[attr_value][3] = True
                        continue
                    added_elements[attr_value] = [path_to_html, el, prepared_name, False]
                for element_data in added_elements.values():
                    res.append(cls._format_element_by_attribute(*element_data))
        return res

    @classmethod
    def _format_element_by_attribute(cls, path_to_html: Path, element: HtmlElement, attr_name: str, many: bool) -> str:
        """
        форматирует найденный элемент html по паттерну атрибута в атрибут генерируемого класса python
        :param path_to_html:
        :param element:
        :param attr_name: имя атрибута
        :param many: флаг, если по значению атрибута было найдено более 1 элемента
        :return:
        """
        xpath = XPATH_BY_TAG_ATTR.format(
            attr_name=attr_name,
            attr_value=element.attrib[attr_name],
        )
        property_name = '_'.join([attr_name, element.attrib[attr_name]])
        attribute_value = cls._format_attribute_value(xpath=xpath, many=many)
        return cls._print_element_in_py_repr(element, property_name, attribute_value, path_to_html, many)

    @classmethod
    def _format_attribute_value(cls, xpath: str, many: bool):
        """
        создает python-представление атрибута
        :param xpath:
        :param many:
        :return:
        """
        proxy_class = ElementDescriptor.__name__
        search_by = By.XPATH
        return f"{proxy_class}(search_by='{search_by}', value=r{xpath}, many={many})"

    @classmethod
    def _print_element_in_py_repr(cls, element: HtmlElement, property_name: str,
                                  attribute_value: str, path_to_html: Path, many: bool):
        """
        форматирует найденный элемент страницы html в python-представление (т.е. в атрибут класса)
        :param element:
        :param property_name: имя свойства, по которомы был найдем html-элемент
        :param attribute_value: имя атрибута, которое будет присвоено в классе
        :param path_to_html: абсолютный путь до html
        :param many: флаг, если по значению атрибута было найдено более 1 элемента
        :return:
        """
        formatted_property_name = Utils.format_name_to_python_format(name=property_name)
        name = Utils.make_attribute_name(tag_name=element.tag, property_name=formatted_property_name)
        relative_path_to_html = path_to_html.relative_to(cls.backend_path)
        annotation = f'{List.__name__}[{WebElementProxy.__name__}]' if many else WebElementProxy.__name__
        kwargs = {
            'attribute_name': name,
            'attribute_annotation': annotation,
            'attribute_value': attribute_value,
            'path_to_attribute': Utils.path_with_row_number(relative_path_to_html, element.sourceline),
        }
        return ATTRIBUTE_REPR.format(**kwargs)
