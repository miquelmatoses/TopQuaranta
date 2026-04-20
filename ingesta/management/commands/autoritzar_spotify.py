"""One-time Spotify OAuth dance to unlock user-scoped endpoints.

Spotify's Authorization Code flow gives us a long-lived `refresh_token`
that the daily playlist sync cron uses to mint short-lived access
tokens on the fly. The refresh token never expires unless the user
revokes it from Spotify's account dashboard.

Loopback flow: the admin opens the URL we print, signs in to Spotify
and approves the requested scope. Spotify redirects to
`http://127.0.0.1:8888/callback?code=<CODE>&state=<STATE>`. No server
runs there — the browser just shows "connection refused". The admin
copies the `code=` value from the URL bar and pastes it into the
prompt below. We exchange it for (access_token, refresh_token) and
persist the refresh token to `music.SpotifyAuth`.
"""

import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ingesta.clients.spotify import API_BASE, TOKEN_URL, UserSpotifyClient
from music.models import SpotifyAuth


class Command(BaseCommand):
    help = "Authorise the TopQuaranta Spotify account for playlist management."

    def handle(self, *args, **opts):
        if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
            raise CommandError(
                "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET no configurats al .env."
            )
        redirect_uri = settings.SPOTIFY_REDIRECT_URI
        state = secrets.token_urlsafe(16)

        params = {
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": UserSpotifyClient.OAUTH_SCOPES,
            "state": state,
        }
        auth_url = "https://accounts.spotify.com/authorize?" + urlencode(params)

        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO(
                "Pas 1 · Obre aquesta URL al navegador i autoritza TopQuaranta:"
            )
        )
        self.stdout.write("")
        self.stdout.write(auth_url)
        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO("Pas 2 · Després d'autoritzar, Spotify redirigirà a:")
        )
        self.stdout.write(f"    {redirect_uri}?code=AQXXXXX&state={state}")
        self.stdout.write("    (el navegador dirà 'connection refused' — és normal)")
        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO(
                "Pas 3 · Copia el valor de `code=` de la URL del navegador i enganxa'l aquí:"
            )
        )
        self.stdout.write("")

        code = input("Code: ").strip()
        if not code:
            raise CommandError("Cap code rebut.")

        # Exchange code → tokens.
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
            timeout=10,
        )
        if response.status_code != 200:
            raise CommandError(
                f"Spotify token exchange falla ({response.status_code}): "
                f"{response.text}"
            )
        payload = response.json()
        refresh_token = payload.get("refresh_token")
        access_token = payload.get("access_token")
        scope = payload.get("scope", "")
        if not refresh_token:
            raise CommandError("Spotify no ha tornat refresh_token.")

        # Fetch spotify_user_id for reference (and so the cron logs who owns this).
        me_resp = requests.get(
            f"{API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        me_resp.raise_for_status()
        spotify_user_id = me_resp.json()["id"]

        SpotifyAuth.objects.update_or_create(
            pk=1,
            defaults={
                "refresh_token": refresh_token,
                "scope": scope,
                "spotify_user_id": spotify_user_id,
            },
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Autoritzat com a Spotify user '{spotify_user_id}'. " f"Scope: {scope}"
            )
        )
        self.stdout.write(
            "Ara pots executar `manage.py actualitzar_playlists_spotify` "
            "per fer una primera sincronització."
        )
