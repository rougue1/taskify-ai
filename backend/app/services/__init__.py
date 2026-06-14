"""Service layer holding business logic, decoupled from the transport layer.

Both the REST routers and the LangGraph agent tools call into these services so
that task logic lives in exactly one place.
"""
