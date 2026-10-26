"""Constantes compartidas del ETL."""

# Expresión SQL para `actualizado_en`: hora local de Madrid (no UTC).
# `now() AT TIME ZONE 'Europe/Madrid'` toma el instante actual y lo convierte a
# la hora de pared de Madrid, devolviéndola como `timestamp` sin zona (que es el
# tipo de la columna). Así el campo se ve en hora española, no en UTC.
ACTUALIZADO_EN = "(now() AT TIME ZONE 'Europe/Madrid')"
