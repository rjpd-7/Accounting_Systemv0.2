from django.test import TestCase

from .models import AccountGroups, ChartOfAccounts
from .views import _validate_unique_accounts_for_rows


class JournalAccountUniquenessValidationTests(TestCase):
	def setUp(self):
		self.group = AccountGroups.objects.create(
			group_name='Test Group',
			group_description='Test Group Description'
		)
		self.cash = ChartOfAccounts.objects.create(
			account_code='100001',
			account_name='Cash',
			account_type='Assets',
			group_name=self.group
		)
		self.supplies = ChartOfAccounts.objects.create(
			account_code='500001',
			account_name='Supplies Expense',
			account_type='Expenses',
			group_name=self.group
		)

	def test_duplicate_accounts_are_rejected(self):
		rows = [
			{'account': self.cash, 'debit': 100, 'credit': 0},
			{'account': self.cash, 'debit': 0, 'credit': 100},
		]

		is_valid, error = _validate_unique_accounts_for_rows(rows)

		self.assertFalse(is_valid)
		self.assertIn('Duplicate account selection is not allowed', error)
		self.assertIn('Cash', error)

	def test_unique_accounts_are_accepted(self):
		rows = [
			{'account': self.cash, 'debit': 100, 'credit': 0},
			{'account': self.supplies, 'debit': 0, 'credit': 100},
		]

		is_valid, error = _validate_unique_accounts_for_rows(rows)

		self.assertTrue(is_valid)
		self.assertEqual(error, '')
