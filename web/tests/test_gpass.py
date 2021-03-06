from unittest import TestCase

# Prepare environment
from flask_testing import TestCase as FlaskTestCase
from mock import patch

from focus.gpass_connect import GpassConnection
from focus.server import application  # noqa: E402
from focus.crypto import encrypt

from .mocks import get_response_mock

TESTKEY = "z4QXWk3bjwFST2HRRVidnn7Se8VFCaHscK39JfODzNs="


@patch('focus.gpass_connect.requests.get', get_response_mock)
@patch('focus.server.get_gpass_api_location', lambda: 'http://localhost')
@patch("focus.crypto.get_key", lambda: TESTKEY)
class GpassConnectionTest(TestCase):
    admin_number = '111111111'

    def setUp(self) -> None:
        pass

    def _get_connection(self):
        return GpassConnection('http://localhost', 'token')

    def test_get_stadspassen(self):
        con = self._get_connection()
        result = con.get_stadspassen(self.admin_number)

        expected = [
            {
                'budgets': [
                    {
                        'assigned': 100,
                        'balance': 0,
                        'code': 'AMSEducatie',
                        'description': 'Educatie budget, voor iedereen uit de gemeente amsterdam en geboren tussen 1-1-2004 en 1-1-2020'
                    }
                ],
                'datumAfloop': '2020-08-31T23:59:59.000Z',
                'id': 999997,
                'naam': 'J. Doe',
                'pasnummer': '6011012604737'},
            {
                'budgets': [
                    {
                        'assigned': 100,
                        'balance': 0,
                        'code': 'AMSEducatie',
                        'description': 'Educatie budget, voor iedereen uit de gemeente amsterdam en geboren tussen 1-1-2004 en 1-1-2020'
                    }
                ],
                'datumAfloop': '2020-08-31T23:59:59.000Z',
                'id': 999999,
                'naam': 'P Achternaam2',
                'pasnummer': '6666666666666666666'
            },
            {
                'budgets': [
                    {
                        'assigned': 100,
                        'balance': 0,
                        'code': 'AMSEducatie',
                        'description': 'Educatie budget, voor iedereen uit de gemeente '
                                       'amsterdam en geboren tussen 1-1-2004 en '
                                       '1-1-2020'
                    }
                ],
                'datumAfloop': '2020-08-31T23:59:59.000Z',
                'id': 999997,
                'naam': 'J Achternaam3',
                'pasnummer': '6011012604737'
            }
        ]

        self.assertTrue(result[0]["budgets"][0]["urlTransactions"].startswith('/api/focus/stadspastransacties/'))
        # remove url, it has a timebased factor in it.
        del (result[0]["budgets"][0]["urlTransactions"])
        del (result[1]["budgets"][0]["urlTransactions"])
        del (result[2]["budgets"][0]["urlTransactions"])

        self.assertEqual(result, expected)

    def test_get_transactions(self):
        pas_number = '6666666666666'
        budget_code = 'aaa'
        con = self._get_connection()
        result = con.get_transactions(self.admin_number, pas_number, budget_code)

        expected = [
            {
                'id': 1,
                'title': 'Fietsenwinkel - B.V.',
                'amount': 20.0,
                'date': '2020-10-05T04:01:01.0000000'
            }
        ]
        self.assertEqual(result, expected)

    def test_get_transactions_wrong_pas_number(self):
        pas_number = 11111
        con = self._get_connection()
        result = con.get_transactions(self.admin_number, pas_number, budget_code='aaa')
        self.assertEqual(result, None)


@patch('focus.gpass_connect.requests.get', get_response_mock)
@patch('focus.server.get_gpass_api_location', lambda: 'http://localhost')
@patch("focus.crypto.get_key", lambda: TESTKEY)
class GpassApiTest(FlaskTestCase):
    admin_number = '111111111'
    pas_number = '6666666666666'
    budget_code = 'aaa'

    def create_app(self):
        return application

    # stadpassen data is in the combined api

    def test_get_transactions(self):
        encrypted = encrypt(self.budget_code, self.admin_number, self.pas_number)
        response = self.client.get(f'/focus/stadspastransacties/{encrypted}')

        expected = {
            'content': [
                {
                    'amount': 20.0,
                    'date': '2020-10-05T04:01:01.0000000',
                    'id': 1,
                    'title': 'Fietsenwinkel - B.V.'
                }
            ],
            'status': 'ok'
        }

        self.assert200(response)
        self.assertEqual(response.json, expected)
