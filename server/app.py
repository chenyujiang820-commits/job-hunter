"""FastAPI application factory for the multi-user pilot."""

from fastapi import FastAPI

from server.adapters.browser_connector import ChromiumBrowserConnector
from server.adapters.llm_provider import OpenAICompatibleLLMProvider, UnavailableLLMProvider
from server.adapters.object_storage import ObjectStorage
from server.api import (
    admin,
    auth,
    browser_sessions,
    collection_tasks,
    documents,
    evaluations,
    invites,
    material_batches,
    profile,
    search_templates,
    settings as settings_api,
)
from server.db import create_session_factory
from server.security.credentials import CredentialCipher
from server.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    app = FastAPI(title=resolved.app_name, version=resolved.app_version)
    app.state.settings = resolved
    app.state.session_factory = create_session_factory(resolved)
    app.state.credential_cipher = CredentialCipher.from_secret(resolved.model_credential_key)
    app.state.object_storage = ObjectStorage.from_settings(resolved)
    app.state.browser_connector = ChromiumBrowserConnector(resolved.chromium_profile_root)
    app.state.llm_provider = (
        OpenAICompatibleLLMProvider(
            api_key=resolved.default_model_key,
            endpoint=resolved.llm_endpoint,
            model=resolved.llm_model,
            key_decoder=app.state.credential_cipher.decrypt if app.state.credential_cipher else None,
        )
        if resolved.default_model_key
        else UnavailableLLMProvider()
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": resolved.app_version}

    app.include_router(auth.router)
    app.include_router(invites.router)
    app.include_router(admin.router)
    app.include_router(documents.router)
    app.include_router(profile.router)
    app.include_router(settings_api.router)
    app.include_router(search_templates.router)
    app.include_router(evaluations.router)
    app.include_router(browser_sessions.router)
    app.include_router(collection_tasks.router)
    app.include_router(material_batches.router)

    return app


app = create_app()
