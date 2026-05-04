"""Connector layer — external data sources.

One module per source family. Each connector is responsible for:
  - authentication (OAuth, admin grant, API keys)
  - retrieval (delta query / webhook / polling)
  - normalisation into our schema (email_messages, events, ...)
  - rate limiting + retry
  - **never** scraping a domain on app.scrapers._restricted.RESTRICTED_DOMAINS
"""
