"""FastAPI application — webhook endpoint, health check, and bot lifecycle management."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.ext import Application, CommandHandler

from app.bot.conversations import (
    build_eliminar_registro_handler,
    build_generar_reporte_handler,
    build_recuperar_registro_handler,
    build_registrar_dia_handler,
    build_registrar_otro_dia_handler,
)
from app.bot.handlers import BOT_COMMANDS, error_handler, start_cmd, ver_semana_cmd
from app.config import get_settings
from app.models.database import close_pool, create_pool

# ── Logging ──────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── Global bot application ───────────────────────────────────────────────────

bot_app: Optional[Application] = None


def _register_handlers(application: Application) -> None:
    """Register all command and conversation handlers on the bot application."""
    # Conversation handlers (must be added before simple command handlers)
    application.add_handler(build_registrar_dia_handler())
    application.add_handler(build_registrar_otro_dia_handler())
    application.add_handler(build_eliminar_registro_handler())
    application.add_handler(build_recuperar_registro_handler())
    application.add_handler(build_generar_reporte_handler())

    # Simple command handlers
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("ver_semana", ver_semana_cmd))

    # Error handler
    application.add_error_handler(error_handler)


# ── Application lifespan ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of the database pool and Telegram bot."""
    global bot_app
    cfg = get_settings()

    # ── Configure logging ────────────────────────────────────────────────
    logging.basicConfig(
        level=getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("Starting Time Cop application...")

    # Database pool
    await create_pool(
        cfg.DATABASE_URL,
        min_size=cfg.DB_POOL_MIN_SIZE,
        max_size=cfg.DB_POOL_MAX_SIZE,
    )

    # Telegram bot
    bot_app = Application.builder().token(cfg.TELEGRAM_BOT_TOKEN).build()
    _register_handlers(bot_app)
    await bot_app.initialize()
    await bot_app.start()

    # Set bot commands menu
    await bot_app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands menu set")

    if cfg.is_webhook_mode:
        # Webhook mode (production)
        webhook_url = f"{cfg.WEBHOOK_URL}/webhook"
        await bot_app.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set: %s", webhook_url)
    else:
        # Polling mode (local development)
        logger.info("No WEBHOOK_URL configured — starting in polling mode")
        await bot_app.updater.start_polling(drop_pending_updates=True)

    logger.info("Time Cop started successfully ✅")

    yield  # ── Application is running ──

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("Shutting down Time Cop...")

    if bot_app:
        if cfg.is_webhook_mode:
            await bot_app.bot.delete_webhook()
        else:
            await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

    await close_pool()
    logger.info("Time Cop shut down ✅")


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Time Cop",
    description="Telegram bot for time tracking with AI-powered activity parsing",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def root() -> dict:
    """Root endpoint to satisfy health checks."""
    return {"message": "Time Cop API is running", "status": "ok"}


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for readiness probes."""
    return {"status": "ok", "service": "time_cop"}


@app.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Receive Telegram updates via webhook.

    This endpoint is only used in webhook mode (production).
    In polling mode, updates are fetched automatically.
    """
    if bot_app is None:
        logger.error("Webhook received but bot is not initialised")
        return Response(status_code=503)

    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
    except Exception as exc:
        logger.error("Error processing webhook update: %s", exc, exc_info=True)

    return Response(status_code=200)
