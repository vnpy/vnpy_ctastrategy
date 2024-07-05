import gettext
from pathlib import Path


localedir = Path(__file__).parent

translations: gettext.GNUTranslations = gettext.translation('vnpy_ctastrategy', localedir=localedir, fallback=True)

_ = translations.gettext
