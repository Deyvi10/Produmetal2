"""
Servicio centralizado de cálculo de nómina.

Fórmulas extraídas y validadas contra el Excel real de la empresa
("ROL DE PAGOS PRODUMETAL RUC KEVIN MORALES 2Q AGOSTO.xlsx", hoja
"Rol de Pagos RUC KM"), reproducidas aquí en un único punto para no
duplicarlas entre vistas.

- Valor Hora = Sueldo Mensual / 240   (240 = 30 días x 8 horas)
- Hora "Ordinaria" (recargo 50%, HE50 en el Excel): horas trabajadas fuera
  de jornada en un día laborable normal.
      Pago = cantidad_horas * valor_hora * 1.5
- Hora "Extraordinaria" (recargo 100%, HE100 en el Excel): horas trabajadas
  en feriado, día de descanso obligatorio (p.ej. sábado en esta empresa) u
  horario nocturno.
      Pago = cantidad_horas * valor_hora * 2.0

Verificado línea por línea contra el Excel: p.ej. sueldo 550 -> valor_hora
2.291666...; 2h "ordinarias" -> 2 * 2.291666... * 1.5 = 6.875 (coincide con
la columna M de la hoja); 8h "extraordinarias" -> 8 * 2.291666... * 2 =
36.666... (coincide con la columna N).
"""

from decimal import Decimal, ROUND_HALF_UP

HORAS_BASE_MENSUAL = Decimal('240')

RECARGOS_HORA_EXTRA = {
    'ORDINARIA': Decimal('1.5'),
    'EXTRAORDINARIA': Decimal('2.0'),
}


def calcular_valor_hora(trabajador):
    """
    Valor de la hora ordinaria de trabajo: Sueldo Mensual vigente / 240.
    Lanza ValueError si el trabajador no tiene un salario asignado (no hay
    forma de calcular el valor de la hora sin uno).
    """
    salario = trabajador.salario_actual
    if not salario:
        raise ValueError("El trabajador no tiene un salario asignado; no se puede calcular el valor de la hora.")
    return (salario.monto / HORAS_BASE_MENSUAL).quantize(Decimal('0.0001'))


def calcular_valor_hora_extra(trabajador, tipo, cantidad_horas):
    """
    Monto a pagar por `cantidad_horas` de hora extra `tipo` ('ORDINARIA' con
    recargo 50%, o 'EXTRAORDINARIA' con recargo 100%), según el salario
    vigente del trabajador.
    """
    recargo = RECARGOS_HORA_EXTRA.get(tipo)
    if recargo is None:
        raise ValueError(f"Tipo de hora extra desconocido: {tipo}")

    valor_hora = calcular_valor_hora(trabajador)
    total = Decimal(cantidad_horas) * valor_hora * recargo
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
