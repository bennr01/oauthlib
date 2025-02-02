# -*- coding: utf-8 -*-
from oauthlib.oauth2 import MetadataEndpoint, Server, TokenEndpoint

import json
from tests.unittest import TestCase


from oauthlib import oauth2


class ServerWithMetadata(oauth2.Server, oauth2.MetadataEndpoint):
    """
    A helper class for testing compatibility between MetadataEndpoint and
    the Server class when inheriting from both.

    This is used for the regression test for https://github.com/oauthlib/oauthlib/pull/808 .
    """
    def __init__(
        self,
        request_validator,
        token_expires_in=None,
        token_generator=None,
        refresh_token_generator=None,
        claims={},
        *args,
        **kwargs,
    ):
        oauth2.Server.__init__(
            self,
            request_validator,
            token_expires_in=token_expires_in,
            token_generator=token_generator,
            refresh_token_generator=refresh_token_generator,
            *args,
            **kwargs,
        )
        oauth2.MetadataEndpoint.__init__(
            self,
            [self],
            claims=claims,
            raise_errors=True,
        )


class MetadataEndpointTest(TestCase):
    def setUp(self):
        self.metadata = {
            "issuer": 'https://foo.bar'
        }

    def test_openid_oauth2_preconfigured(self):
        default_claims = {
            "issuer": 'https://foo.bar',
            "authorization_endpoint": "https://foo.bar/authorize",
            "revocation_endpoint": "https://foo.bar/revoke",
            "introspection_endpoint": "https://foo.bar/introspect",
            "token_endpoint": "https://foo.bar/token"
        }
        from oauthlib.oauth2 import Server as OAuth2Server
        from oauthlib.openid import Server as OpenIDServer

        endpoint = OAuth2Server(None)
        metadata = MetadataEndpoint([endpoint], default_claims)
        oauth2_claims = metadata.claims

        endpoint = OpenIDServer(None)
        metadata = MetadataEndpoint([endpoint], default_claims)
        openid_claims = metadata.claims

        # Pure OAuth2 Authorization Metadata are similar with OpenID but
        # response_type not! (OIDC contains "id_token" and hybrid flows)
        del oauth2_claims['response_types_supported']
        del openid_claims['response_types_supported']

        self.maxDiff = None
        self.assertEqual(openid_claims, oauth2_claims)

    def test_create_metadata_response(self):
        endpoint = TokenEndpoint(None, None, grant_types={"password": None})
        metadata = MetadataEndpoint([endpoint], {
            "issuer": 'https://foo.bar',
            "token_endpoint": "https://foo.bar/token"
        })
        headers, body, status = metadata.create_metadata_response('/', 'GET')
        assert headers == {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        }
        claims = json.loads(body)
        assert claims['issuer'] == 'https://foo.bar'

    def test_token_endpoint(self):
        endpoint = TokenEndpoint(None, None, grant_types={"password": None})
        metadata = MetadataEndpoint([endpoint], {
            "issuer": 'https://foo.bar',
            "token_endpoint": "https://foo.bar/token"
        })
        self.assertIn("grant_types_supported", metadata.claims)
        self.assertEqual(metadata.claims["grant_types_supported"], ["password"])

    def test_token_endpoint_overridden(self):
        endpoint = TokenEndpoint(None, None, grant_types={"password": None})
        metadata = MetadataEndpoint([endpoint], {
            "issuer": 'https://foo.bar',
            "token_endpoint": "https://foo.bar/token",
            "grant_types_supported": ["pass_word_special_provider"]
        })
        self.assertIn("grant_types_supported", metadata.claims)
        self.assertEqual(metadata.claims["grant_types_supported"], ["pass_word_special_provider"])

    def test_mandatory_fields(self):
        metadata = MetadataEndpoint([], self.metadata)
        self.assertIn("issuer", metadata.claims)
        self.assertEqual(metadata.claims["issuer"], 'https://foo.bar')

    def test_server_metadata(self):
        endpoint = Server(None)
        metadata = MetadataEndpoint([endpoint], {
            "issuer": 'https://foo.bar',
            "authorization_endpoint": "https://foo.bar/authorize",
            "introspection_endpoint": "https://foo.bar/introspect",
            "revocation_endpoint": "https://foo.bar/revoke",
            "token_endpoint": "https://foo.bar/token",
            "jwks_uri": "https://foo.bar/certs",
            "scopes_supported": ["email", "profile"]
        })
        expected_claims = {
            "issuer": "https://foo.bar",
            "authorization_endpoint": "https://foo.bar/authorize",
            "introspection_endpoint": "https://foo.bar/introspect",
            "revocation_endpoint": "https://foo.bar/revoke",
            "token_endpoint": "https://foo.bar/token",
            "jwks_uri": "https://foo.bar/certs",
            "scopes_supported": ["email", "profile"],
            "grant_types_supported": [
                "authorization_code",
                "password",
                "client_credentials",
                "refresh_token",
                "implicit"
            ],
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic"
            ],
            "response_types_supported": [
                "code",
                "token"
            ],
            "response_modes_supported": [
                "query",
                "fragment"
            ],
            "code_challenge_methods_supported": [
                "plain",
                "S256"
            ],
            "revocation_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic"
            ],
            "introspection_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic"
            ]
        }

        def sort_list(claims):
            for k in claims.keys():
                claims[k] = sorted(claims[k])

        sort_list(metadata.claims)
        sort_list(expected_claims)
        self.assertEqual(sorted(metadata.claims.items()), sorted(expected_claims.items()))

    def test_metadata_validate_issuer(self):
        with self.assertRaises(ValueError):
            endpoint = TokenEndpoint(
                None, None, grant_types={"password": None},
            )
            metadata = MetadataEndpoint([endpoint], {
                "issuer": 'http://foo.bar',
                "token_endpoint": "https://foo.bar/token",
            })

    def test_inheritance_compatibility_with_server(self):
        """
        Test compatibility between the MetadataEndpoint and Server in subclasses
        inheriting from both classes.

        This is a regression test for https://github.com/oauthlib/oauthlib/pull/808 .
        The bug fixed in the linked PR occured when a class inheriting from both Server
        and MetadataEndpoint called MetadataEndpoint.__init__() and passing itself as an
        argument.
        The underlying cause of the bug was an attribute collision between the
        TokenEndpoint and the MetadataEndpoint, both of which use the _grant_types
        attribute, but using different types (list and dict).
        """
        # checking against a regression is rather simple in this case, as the bug happens
        # during __init__ of the MetadataEndpoint.
        # we can just create an instance of ServerWithMetadata. If this succeeds without
        # a bug, then this test was successful.
        validator = None
        claims = {
            "issuer": 'https://foo.bar',
            "authorization_endpoint": "https://foo.bar/authorize",
            "revocation_endpoint": "https://foo.bar/revoke",
            "introspection_endpoint": "https://foo.bar/introspect",
            "token_endpoint": "https://foo.bar/token"
        }
        ServerWithMetadata(validator, claims=claims)
