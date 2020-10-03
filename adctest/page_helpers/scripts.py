PAGE_READY_SCRIPT = "if ('e2eReady' in window && window.e2eReady === true){return true;}else{return false;}"

SCROLL_TEMPLATE_SCRIPT = """
arguments[0].scrollIntoView({{block: "{block}", inline: "{inline}"}})
"""
