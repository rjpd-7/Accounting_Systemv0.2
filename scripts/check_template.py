import os
import sys
# ensure project root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Accounting_System.settings')
import django
from django.template import TemplateSyntaxError
from django.template.loader import get_template

try:
    django.setup()
    t = get_template('Front_End/balance_sheet_pdf.html')
    print('Template loaded successfully')
except TemplateSyntaxError as e:
    print('TEMPLATE SYNTAX ERROR:')
    print(e)
    sys.exit(2)
except Exception as e:
    print('ERROR:')
    print(type(e), e)
    sys.exit(1)
