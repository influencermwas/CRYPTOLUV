"""
Compatibility shim for Python 3.13+.
python-telegram-bot==13.15 imports imghdr, but Python 3.13+ removed it.
This minimal file prevents ModuleNotFoundError.
"""

def what(file, h=None):
    return None
