PAGE_READY_SCRIPT = "if ('e2eReady' in window && window.e2eReady === true){return true;}else{return false;}"

SCROLL_TEMPLATE_SCRIPT = """
arguments[0].scrollIntoView({{block: "{block}", inline: "{inline}"}})
"""


class check_js_condition_is_true:
    """Проверка js-условия"""
    def __init__(self, js_code: str):
        self.code = js_code

    def __call__(self, driver):
        result = driver.execute_script(self.code)
        if result is True:
            return True
        else:
            return False
