""" Focus Connection

This module represents a connection with Focus.
The connection can be established, re-established (reset method)
The connection exposes the aanvragen and document methods of the underlying Focus SOAP API
"""
import base64
import re
import logging
import xmltodict
from bs4 import BeautifulSoup

from requests import Session, ConnectionError
from requests.auth import HTTPBasicAuth
from zeep import Client
from zeep.transports import Transport

from .focusinterpreter import convert_aanvragen, convert_jaaropgaven, convert_uitkeringsspecificaties, convert_e_aanvraag_TOZO, convert_stadspas
from .measure_time import MeasureTime

logger = logging.getLogger(__name__)


LOG_RAW = False


class FocusConnection:
    """ This class encapsulates the (SOAP) connection with Focus"""

    def __init__(self, config, credentials):
        """
        Initializes the Focus SOAP connection
        :param config: SOAP service configuration
        :param credentials: credentials to use for connecting to the SOAP service
        """
        self._config = config
        self._credentials = credentials
        self._client = self._initialize_client()

    def _initialize_client(self):
        """
        Use the configuration details that have been supplied at object creation time to establish a
        connection to the Focus SOAP API.
        The resulting service should be registered by the caller with the object in self._client
        :return: Object
        """
        logger.info('Establishing a connection with Focus')

        session = Session()
        session.auth = HTTPBasicAuth(self._credentials['username'], self._credentials['password'])

        timeout = 9    # Timeout period for getting WSDL and operations in seconds

        try:
            transport = Transport(session=session, timeout=timeout, operation_timeout=timeout)

            client = Client(wsdl=self._config['wsdl'], transport=transport)

            return client
        except ConnectionError as e:
            # do not relog the error, because the error has a object address in it, it is a new error every time.
            logger.error(f'Failed to establish a connection with Focus: Connection Time Out ({type(e)})')
            return None
        except Exception as error:
            logger.error('Failed to establish a connection with Focus: {} {}'.format(type(error), str(error)))
            return None

    def reset(self):
        self._client = self._initialize_client()

    def is_alive(self):
        """
        Tells whether the connection with Focus is available.
        :return: boolean
        """
        return self._client is not None

    def _log_soap_faultstring(self, raw_xml, prefix=''):
        result = re.search(r'<faultstring>.*<\/faultstring>', raw_xml)
        if result:
            faultstring = result.group(0)

            # remove the ever changing number
            faultstring = re.sub(r'nl.amsterdam.dwi.onlineklantbeeld.model.DocumentLocatie#\d+', 'nl.amsterdam.dwi.onlineklantbeeld.model.DocumentLocatie', faultstring)

            logger.error(f'{prefix} {faultstring}')
        else:
            logger.error(f'{prefix} {raw_xml}')

    def aanvragen(self, bsn, url_root):
        """
        Retrieve the aanvragen from Focus
        :param bsn: string
        :param url_root: string: Used to construct href for corresponding documents
        :return: Dictionary
        """

        with self._client.settings(raw_response=True):
            # Get raw response as string remove any newlines
            raw_aanvragen = self._client.service.getAanvragen(bsn=bsn).content.decode("utf-8").replace("\n", "")
            # Get the return component out of the SOAP message
            result = re.search(r"<return>.*<\/return>", raw_aanvragen)
            if not result:
                # This can return something else apparently. Lets log this so we can debug this.
                self._log_soap_faultstring(raw_aanvragen, "no body?")
                return []
            xml_aanvragen = result.group(0)
            # Translate the response to a Dictionary
            aanvragen = xmltodict.parse(xml_aanvragen)["return"]
            # Convert dict types for lists, ints and bools
            aanvragen = convert_aanvragen(aanvragen, url_root)

        return aanvragen

    def jaaropgaven(self, bsn, url_root):
        with self._client.settings(raw_response=True):
            raw_jaaropgaven = self._client.service.getJaaropgaven(bsn=bsn).content.decode("utf-8").replace("\n", "")
            result = re.search(r"<return>.*<\/return>", raw_jaaropgaven)
            if not result:
                # This can return something else apparently. Lets log this so we can debug this.
                self._log_soap_faultstring(raw_jaaropgaven, "no body jaaropgaven?")
                return []
            xml_jaaropgaven = result.group(0)
            jaaropgaven = convert_jaaropgaven(xml_jaaropgaven, url_root)
            return jaaropgaven

    def uitkeringsspecificaties(self, bsn, url_root):
        with self._client.settings(raw_response=True):
            raw_specificaties = self._client.service.getUitkeringspecificaties(bsn=bsn).content.decode("utf-8").replace("\n", "")

            result = re.search(r"<return>.*<\/return>", raw_specificaties)
            if not result:
                # This can return something else apparently. Lets log this so we can debug this.
                self._log_soap_faultstring(raw_specificaties, "no body uitkeringspec?")
                return []
            xml_uitkeringspec = result.group(0)
            uitkeringsspecificaties = convert_uitkeringsspecificaties(xml_uitkeringspec, url_root)
            return uitkeringsspecificaties

    def EAanvragenTozo(self, bsn, url_root):
        with self._client.settings(raw_response=True):
            raw_tozo_documenten = self._client.service.getEAanvraagTOZO(bsn=bsn).content.decode("utf-8").replace("\n", "")
            tree = BeautifulSoup(raw_tozo_documenten, features="lxml-xml")
            aanvragen = tree.find('getEAanvraagTOZOResponse')
            if not aanvragen:
                try:
                    faultsstring = tree.find('faultstring')
                    logger.debug(faultsstring)
                except Exception as e:
                    logger.exception(e)
                return []
            tozo_documenten = convert_e_aanvraag_TOZO(tree, url_root)
            return tozo_documenten

    def stadspas(self, bsn):
        with self._client.settings(raw_response=True):
            with MeasureTime("stadspas soap"):
                raw_stadspas = self._client.service.getStadspas(bsn=bsn).content.decode("utf-8").replace("\n", "")
            tree = BeautifulSoup(raw_stadspas, features="lxml-xml")
            if LOG_RAW:
                print(tree.prettify())
            stadspas = tree.find('getStadspasResponse')
            if not stadspas:
                self._log_soap_faultstring(raw_stadspas, 'no stadspas?')
            data = convert_stadspas(tree)

            return data

    def document(self, bsn, id, isBulk, isDms):
        """
        Retrieve a document from Focus
        :param bsn: string
        :param id: integer
        :param isBulk: boolean
        :param isDms: boolean
        :return: Dictionary
        """
        header_value = {'Accept': 'application/xop+xml'}

        # Get the document
        with self._client.settings(raw_response=True, extra_http_headers=header_value):
            raw_document = self._client.service.getDocument(id=id, bsn=bsn, isBulk=isBulk, isDms=isDms)

        tree = BeautifulSoup(raw_document.content, features="lxml-xml")
        data_element = tree.find('dataHandler')
        if not data_element:
            doc = self._client.service.getDocument(id=id, bsn=bsn, isBulk=isBulk, isDms=isDms)
            if doc and doc['dataHandler']:
                data = doc['dataHandler']
                filename = doc['fileName']
                logger.error("fallback document method is used")
            else:
                return None
        else:
            data = data_element.text
            data = base64.b64decode(data)
            filename = tree.find('fileName').text
        mime_type = "application/pdf" if ".pdf" in filename else "application/octet-stream"

        document = {
            "fileName": filename,
            "contents": data,
            "mime_type": mime_type,
        }

        return document
