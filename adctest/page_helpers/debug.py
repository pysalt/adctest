import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict
from uuid import uuid4

from selenium.common.exceptions import WebDriverException

from adctest.config import config
from adctest.driver.driver import E2EDriver

logger = logging.getLogger('e2e-test')


class ActionTypes(Enum):
    screenshot = 1
    logs = 2


PARAMS = {
    ActionTypes.screenshot: {
        'extension': 'png',
        'path': config.SCREENSHOT_PATH,
        'file_prefix': 'screenshot',
    },
    ActionTypes.logs: {
        'extension': 'log',
        'path': config.CONSOLE_LOG_PATH,
        'file_prefix': 'log',
    }
}


def _generate_file_name(name_part: str, action_type: ActionTypes):
    time_stamp = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
    file_name = '_'.join([PARAMS[action_type]['file_prefix'], name_part, time_stamp])
    ext = PARAMS[action_type]['extension']
    return f'{file_name}.{ext}'


def _append_uniq_postfix(file_name: str) -> str:
    file_name = Path(file_name)
    extension = file_name.suffix
    origin_name = file_name.stem
    postfix = uuid4().hex[:8]
    return f'{origin_name}_{postfix}.{extension}'


def _get_base_path(action_type: ActionTypes):
    path = Path(PARAMS[action_type]['path'])
    if not path.exists():
        path.mkdir(parents=True)
    return path


def _get_write_path(name_part: str, rewrite: bool, action_type: ActionTypes) -> str:
    base_path = _get_base_path(action_type)
    file_name = _generate_file_name(name_part, action_type)
    path = base_path.joinpath(file_name)

    if not rewrite and path.exists():
        new_name = _append_uniq_postfix(file_name)
        path = base_path.joinpath(new_name)

    logger.info(f'Generated path for screenshot/logs: {str(path)}')
    return str(path)


def take_screenshot(name_part: str = "", rewrite: bool = False) -> None:
    """
    делает скриншот страницы браузера в момент вызова
    :param name_part: Часть имени файла, к которой будет дописана дата
    :param rewrite: переписывать файл, если уже создан
    :return:
    """
    driver = E2EDriver.get_driver()
    try:
        path = _get_write_path(name_part=name_part, rewrite=rewrite, action_type=ActionTypes.screenshot)
        driver.save_screenshot(path)
    except WebDriverException as ex:
        logger.warning('Cannot save screenshot. Ex: %s', str(ex))


def save_browser_logs(name_part: str = "", rewrite: bool = False) -> None:
    """
    Получает вывод консоли браузера на момент своего вызова
    :param name_part:
    :param rewrite:
    :return:
    """
    driver = E2EDriver.get_driver()
    try:
        logs: List[Dict] = driver.get_log('browser')
    except WebDriverException as ex:
        logger.warning('Cannot save browser logs. Ex: %s', str(ex))
        return

    if logs:
        path = _get_write_path(name_part=name_part, rewrite=rewrite, action_type=ActionTypes.logs)
        with Path(path).open('w') as f:
            f.write(json.dumps(logs))
