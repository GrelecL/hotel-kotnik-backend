"""
Email worker entrypoint — runs only the IMAP polling loop.
Used as the command for the email-worker Docker service so it
can be scaled/restarted independently of the API.
"""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)

from app.services.email_ingest import email_poll_loop

if __name__ == "__main__":
    asyncio.run(email_poll_loop())
