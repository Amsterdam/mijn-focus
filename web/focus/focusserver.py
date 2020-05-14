""" Focus Server

This module represents the Focus API Server
The server uses the Focus connection class to handle the physical connection with the underlying Focus SOAP API
The server interprets requests, execute the corresponding action and return JSON responses
"""
import logging
from flask import jsonify, request, Response, make_response

from focus.saml import get_bsn_from_request

logger = logging.getLogger(__name__)


class FocusServer:
    def __init__(self, focus_connection, tma_certificate):
        """
        Initializes the Server
        :param focus_connection: The connection to use to access the underlying Focus SOAP API
        :param tma_certificate: The certificate to use to decode SAML tokens (BSN)
        """
        self._focus_connection = focus_connection
        self._tma_certificate = tma_certificate

    def is_alive(self):
        return self._focus_connection.is_alive()

    def _no_connection_response(self):
        """
        Returns a response telling that the Focus API is not accessible
        Reset the connection so that it will be re-established on the next call
        """
        self._focus_connection.reset()
        return Response(
            'Focus connectivity failed',
            content_type='text/plain',
            status=500
        )

    @staticmethod
    def _parameter_error_response(message):
        """
        Returns a response telling that the supplied parameter is incorrect
        """
        return Response(
            'Parameter error: {}'.format(message),
            content_type='text/plain',
            status=422
        )

    @staticmethod
    def health():
        """
        If the server responds to this message (which is always does) it is considered alive (healthy)
        :return: OK
        """
        return Response('OK', content_type='text/plain')

    def status_data(self):
        """
        If the connection with the Focus SOAP API is alive it is assumed that the data is available
        :return: Response
        """
        try:
            if self._focus_connection.is_alive():
                return Response('Connectivity to Focus OK',
                                content_type='text/plain')
        except Exception:
            pass

        return self._no_connection_response()

    def aanvragen(self):
        """
        Gets all running and past aanvragen for the BSN that is encoded in the header SAML token
        :return:
        """
        try:
            bsn = get_bsn_from_request(request)
        except Exception as error:
            return self._parameter_error_response(error)

        aanvragen = self._focus_connection.aanvragen(
            bsn=bsn,
            url_root=request.script_root
        )
            # logger.error("Failed to retrieve aanvragen: {} {}".format(type(error), str(error)))
            # return self._no_connection_response()

        return jsonify(aanvragen)

    def combined(self):
        """ Gets all jaaropgaven for the BSN that is encoded in the header SAML token. """
        try:
            bsn = get_bsn_from_request(request)
        except Exception as error:
            return self._parameter_error_response(error)

        try:
            jaaropgaven = self._focus_connection.jaaropgaven(bsn=bsn, url_root=request.script_root)
            uitkeringsspec = self._focus_connection.uitkeringsspecificaties(bsn=bsn, url_root=request.script_root)
            tozo_documents = self._focus_connection.EAanvragenTozo(bsn=bsn, url_root=request.script_root)
            return {
                "status": "OK",
                "content": {
                    "jaaropgaven": jaaropgaven,
                    "uitkeringsspecificaties": uitkeringsspec,
                    "tozodocumenten": tozo_documents,
                }
            }
        except Exception as error:
            logger.error("Failed to retrieve aanvragen: {} {}".format(type(error), str(error)))
            return self._no_connection_response()

    def document(self):
        """
        Gets a specific aanvraag document for the BSN that is encoded in the header SAML token
        The document is identified by its id and whether it is a bulk or document management document (request args)
        :return:
        """
        id = request.args.get('id', None)
        isBulk = request.args.get('isBulk', "false").lower() == "true"
        isDms = request.args.get('isDms', "false").lower() == "true"

        try:
            bsn = get_bsn_from_request(request)
        except Exception as error:
            return self._parameter_error_response(error)

        try:
            document = self._focus_connection.document(
                bsn=bsn,
                id=id,
                isBulk=isBulk,
                isDms=isDms
            )
        except Exception as error:
            logger.error("Failed to retrieve document: {} {}".format(type(error), str(error)))
            return self._no_connection_response()

        # flask.send_file() won't work with content from memory and uWSGI. It expects a file on disk.
        # Craft a manual request instead
        response = make_response(document["contents"])
        response.headers["Content-Disposition"] = f'attachment; filename="{document["fileName"]}"'  # make sure it is a download
        response.headers["Content-Type"] = document["mime_type"]

        return response
