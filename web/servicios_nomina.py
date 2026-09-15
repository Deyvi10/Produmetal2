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

import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import send_mail

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


def calcular_salario_periodo(trabajador, dias_laborados):
    """
    Salario a pagar por un periodo dado: el sueldo completo si el trabajador
    es MENSUAL, o prorrateado por Valor Día (Sueldo Mensual / 30) si es
    QUINCENAL/SEMANAL. Único punto de cálculo: lo usan tanto la vista previa
    de un pago como Trabajador.registrar_pago al confirmarlo, para que
    ambos den siempre el mismo número.
    """
    salario = trabajador.salario_actual
    if not salario:
        raise ValueError("El trabajador no tiene un salario asignado.")
    if trabajador.periodicidad_pago == 'MENSUAL':
        return salario.monto
    valor_dia = salario.monto / Decimal('30')
    return (valor_dia * Decimal(dias_laborados)).quantize(Decimal('0.01'))


def calcular_horas_dia(horario_dia, hora_entrada, hora_salida):
    """
    Reparte las horas trabajadas un día concreto entre horas normales y
    horas extra, según el horario normal configurado para ese día de la
    semana (HorarioTrabajadorDia, o None si el trabajador no tiene horario).

    - Día normal de trabajo (trabaja=True, con horario definido): el tiempo
      dentro de la ventana [hora_inicio, hora_fin] es horas NORMALES; lo que
      sobra (llegó antes o salió después) es hora "ORDINARIA" (recargo 50%).
    - Día que NO es de trabajo normal (fin de semana, día libre, o sin
      horario configurado): todo el tiempo trabajado es "EXTRAORDINARIA"
      (recargo 100%) — igual que en el Excel real de la empresa.

    Devuelve (horas_normales, horas_ordinarias, horas_extraordinarias) como
    Decimal, redondeadas a 2 decimales. No calcula el valor monetario aquí:
    para eso se usa calcular_valor_hora_extra con el tipo correspondiente.
    """
    ref_dia = datetime.date(2000, 1, 1)
    entrada = datetime.datetime.combine(ref_dia, hora_entrada)
    salida = datetime.datetime.combine(ref_dia, hora_salida)
    if salida <= entrada:
        salida += datetime.timedelta(days=1)  # turno que cruza la medianoche
    total_horas = Decimal(str((salida - entrada).total_seconds() / 3600)).quantize(Decimal('0.01'))

    es_dia_normal = bool(horario_dia and horario_dia.trabaja and horario_dia.hora_inicio and horario_dia.hora_fin)
    if not es_dia_normal:
        return Decimal('0.00'), Decimal('0.00'), total_horas

    h_inicio = datetime.datetime.combine(ref_dia, horario_dia.hora_inicio)
    h_fin = datetime.datetime.combine(ref_dia, horario_dia.hora_fin)
    if h_fin <= h_inicio:
        h_fin += datetime.timedelta(days=1)

    overlap_inicio = max(entrada, h_inicio)
    overlap_fin = min(salida, h_fin)
    horas_normales = Decimal('0.00')
    if overlap_fin > overlap_inicio:
        horas_normales = Decimal(str((overlap_fin - overlap_inicio).total_seconds() / 3600)).quantize(Decimal('0.01'))

    horas_ordinarias = total_horas - horas_normales
    if horas_ordinarias < 0:
        horas_ordinarias = Decimal('0.00')

    return horas_normales, horas_ordinarias, Decimal('0.00')


def enviar_email_pago_confirmado(pago):
    """
    Notifica al trabajador que se le realizó un pago. Lanza la excepción tal
    cual si el envío falla (el llamador decide cómo mostrarla/registrarla) en
    vez de tragarse el error silenciosamente.
    """
    trabajador = pago.trabajador
    if not trabajador.email:
        raise ValueError("El trabajador no tiene un correo electrónico registrado.")

    asunto = "ProduMetal CM - Confirmación de pago realizado"
    mensaje = (
        f"Estimado(a) {trabajador.nombre_completo},\n\n"
        f"Le confirmamos que ProduMetal CM ha realizado el pago correspondiente "
        f"al periodo {pago.periodo_inicio.strftime('%d/%m/%Y')} - {pago.periodo_fin.strftime('%d/%m/%Y')}, "
        f"por un valor total de ${pago.total_pagado}.\n\n"
        f"Gracias por formar parte de nuestro equipo. ¡Seguimos adelante juntos!\n\n"
        f"Atentamente,\nProduMetal CM"
    )
    send_mail(
        asunto, mensaje,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@produmetalcm.com'),
        [trabajador.email],
        fail_silently=False,
    )
