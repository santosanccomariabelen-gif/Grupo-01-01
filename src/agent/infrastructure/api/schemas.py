"""Contrato HTTP del agente (adaptador de entrada).

TODO S1
- ChatRequest: session_id opcional (UUID) y message (sin espacios sobrantes, 1 a 2000 caracteres).
- ChatResponse: session_id, intent y answer.

TODO S2
- ChatResponse.usage: modelos, latencia y tokens del turno.
- ErrorResponse: tipo de falla y detalle.

Regla: estos contratos solo crecen con campos opcionales (T2 citations, T3 pending_action).
"""
