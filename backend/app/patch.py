# backend/app/patch.py

# This file has one purpose: to ensure eventlet monkey-patching happens
# before any other module in the application is imported.
import eventlet
eventlet.monkey_patch()