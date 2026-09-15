from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, Client
from django.urls import reverse

from datetime import date

from .models import (
    Bodega, Categoria, Material, StockBodega, Proyecto,
    Requerimiento, DetalleRequerimiento, CierreIncompletoRequerimiento,
    PerfilEmpleado, Trabajador, EntregaDirecta, MovimientoInventario,
    PrestamoHerramienta, DevolucionPrestamo, Pago, HoraExtra, Descuento,
    PeriodoNominaMensual,
)
from . import servicios_nomina


class EntregasParcialesTestCase(TestCase):
    def setUp(self):
        self.grupo_bodeguero = Group.objects.create(name='Bodeguero')
        self.grupo_solicitante = Group.objects.create(name='Solicitante')

        self.bodega = Bodega.objects.create(nombre='Bodega Central', is_principal=True)

        self.bodeguero = User.objects.create_user('bodeguero1', password='clave12345')
        self.bodeguero.groups.add(self.grupo_bodeguero)
        PerfilEmpleado.objects.create(usuario=self.bodeguero, bodega_asignada=self.bodega)

        self.solicitante = User.objects.create_user('tecnico1', password='clave12345')
        self.solicitante.groups.add(self.grupo_solicitante)

        self.categoria = Categoria.objects.create(nombre='Ferretería', prefijo='FER')
        self.material = Material.objects.create(categoria=self.categoria, nombre='Tornillo 1/2')

        self.proyecto = Proyecto.objects.create(nombre='Obra Test')

        self.client = Client()
        self.client.force_login(self.bodeguero)

    def _crear_requerimiento(self, cantidad_solicitada, stock_inicial):
        StockBodega.objects.create(material=self.material, bodega=self.bodega, cantidad=stock_inicial)

        req = Requerimiento.objects.create(solicitante=self.solicitante, proyecto=self.proyecto)
        detalle = DetalleRequerimiento.objects.create(
            requerimiento=req, material=self.material, bodega_destino=self.bodega,
            cantidad_solicitada=cantidad_solicitada, estado_item='APROBADO_BODEGA'
        )
        return req, detalle

    def test_entrega_parcial_va_acumulando_hasta_completar(self):
        req, detalle = self._crear_requerimiento(cantidad_solicitada=10, stock_inicial=20)

        url = reverse('despachar_requerimiento', args=[req.id])

        # Primera entrega: 2 unidades
        resp = self.client.post(url, {f'cantidad_{detalle.id}': '2'})
        self.assertEqual(resp.status_code, 302)
        detalle.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(detalle.cantidad_despachada, Decimal('2.00'))
        self.assertEqual(detalle.cantidad_pendiente, Decimal('8.00'))
        self.assertEqual(detalle.estado_item, 'APROBADO_BODEGA')
        self.assertEqual(req.estado, 'PARCIALMENTE_DESPACHADO')

        # Segunda entrega: 8 unidades (completa el requerimiento)
        resp = self.client.post(url, {f'cantidad_{detalle.id}': '8'})
        self.assertEqual(resp.status_code, 302)
        detalle.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(detalle.cantidad_despachada, Decimal('10.00'))
        self.assertEqual(detalle.cantidad_pendiente, Decimal('0.00'))
        self.assertEqual(detalle.estado_item, 'DESPACHADO')
        self.assertEqual(req.estado, 'DESPACHADO')

        stock = StockBodega.objects.get(material=self.material, bodega=self.bodega)
        self.assertEqual(stock.cantidad, Decimal('10.00'))  # 20 inicial - 10 entregado

    def test_no_permite_entregar_mas_de_lo_pendiente(self):
        req, detalle = self._crear_requerimiento(cantidad_solicitada=10, stock_inicial=20)
        url = reverse('despachar_requerimiento', args=[req.id])

        self.client.post(url, {f'cantidad_{detalle.id}': '9'})
        detalle.refresh_from_db()
        self.assertEqual(detalle.cantidad_despachada, Decimal('9.00'))

        # Intentar entregar 2 más cuando solo queda 1 pendiente
        resp = self.client.post(url, {f'cantidad_{detalle.id}': '2'}, follow=True)
        detalle.refresh_from_db()
        self.assertEqual(detalle.cantidad_despachada, Decimal('9.00'))  # sin cambios
        mensajes = [str(m) for m in resp.context['messages']]
        self.assertTrue(any('pendientes' in m for m in mensajes))

    def test_no_permite_entregar_mas_del_stock_disponible(self):
        req, detalle = self._crear_requerimiento(cantidad_solicitada=10, stock_inicial=3)
        url = reverse('despachar_requerimiento', args=[req.id])

        resp = self.client.post(url, {f'cantidad_{detalle.id}': '5'}, follow=True)
        detalle.refresh_from_db()
        self.assertEqual(detalle.cantidad_despachada, Decimal('0.00'))
        stock = StockBodega.objects.get(material=self.material, bodega=self.bodega)
        self.assertEqual(stock.cantidad, Decimal('3.00'))
        mensajes = [str(m) for m in resp.context['messages']]
        self.assertTrue(any('existencias' in m for m in mensajes))


class CierreIncompletoTestCase(TestCase):
    def setUp(self):
        self.grupo_bodeguero = Group.objects.create(name='Bodeguero')
        self.bodega = Bodega.objects.create(nombre='Bodega Central', is_principal=True)

        self.bodeguero = User.objects.create_user('bodeguero1', password='clave12345')
        self.bodeguero.groups.add(self.grupo_bodeguero)
        PerfilEmpleado.objects.create(usuario=self.bodeguero, bodega_asignada=self.bodega)

        self.solicitante = User.objects.create_user('tecnico1', password='clave12345')
        self.categoria = Categoria.objects.create(nombre='Ferretería', prefijo='FER')
        self.material = Material.objects.create(categoria=self.categoria, nombre='Tornillo 1/2')
        self.proyecto = Proyecto.objects.create(nombre='Obra Test')

        StockBodega.objects.create(material=self.material, bodega=self.bodega, cantidad=20)
        self.req = Requerimiento.objects.create(solicitante=self.solicitante, proyecto=self.proyecto)
        self.detalle = DetalleRequerimiento.objects.create(
            requerimiento=self.req, material=self.material, bodega_destino=self.bodega,
            cantidad_solicitada=10, cantidad_despachada=4, estado_item='APROBADO_BODEGA'
        )

        self.client = Client()
        self.client.force_login(self.bodeguero)

    def test_cierre_incompleto_requiere_checkbox_y_justificativo(self):
        url = reverse('cerrar_requerimiento_incompleto', args=[self.req.id])

        # Sin checkbox ni justificativo -> rechazado
        resp = self.client.post(url, {}, follow=True)
        self.req.refresh_from_db()
        self.assertNotEqual(self.req.estado, 'CERRADO_INCOMPLETO')

        # Con checkbox pero justificativo corto -> rechazado
        resp = self.client.post(url, {'confirmo_cierre': 'on', 'justificativo': 'corto'}, follow=True)
        self.req.refresh_from_db()
        self.assertNotEqual(self.req.estado, 'CERRADO_INCOMPLETO')

        # Con checkbox y justificativo válido -> se cierra
        resp = self.client.post(url, {
            'confirmo_cierre': 'on',
            'justificativo': 'El cliente canceló el resto del pedido de forma verbal.',
        }, follow=True)
        self.req.refresh_from_db()
        self.assertEqual(self.req.estado, 'CERRADO_INCOMPLETO')

        cierre = CierreIncompletoRequerimiento.objects.get(requerimiento=self.req)
        self.assertEqual(cierre.usuario, self.bodeguero)
        self.assertEqual(cierre.cantidad_solicitada_snapshot, Decimal('10.00'))
        self.assertEqual(cierre.cantidad_despachada_snapshot, Decimal('4.00'))
        self.assertEqual(cierre.cantidad_pendiente_snapshot, Decimal('6.00'))

        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.estado_item, 'CERRADO_INCOMPLETO')

    def test_no_permite_cerrar_dos_veces(self):
        self.req.cerrar_incompleto(usuario=self.bodeguero, justificativo='Motivo válido de cierre.')
        self.assertFalse(self.req.puede_cerrarse_incompleto)

        with self.assertRaises(ValueError):
            self.req.cerrar_incompleto(usuario=self.bodeguero, justificativo='Otro motivo cualquiera.')

    def test_no_permite_cerrar_incompleto_sin_pendientes(self):
        self.detalle.cantidad_despachada = Decimal('10.00')
        self.detalle.estado_item = 'DESPACHADO'
        self.detalle.save()
        self.req.actualizar_estado_general()

        self.assertFalse(self.req.puede_cerrarse_incompleto)
        with self.assertRaises(ValueError):
            self.req.cerrar_incompleto(usuario=self.bodeguero, justificativo='Motivo válido de cierre.')


class EntregaDirectaTestCase(TestCase):
    def setUp(self):
        grupo_bodeguero = Group.objects.create(name='Bodeguero')
        self.bodega = Bodega.objects.create(nombre='Bodega Central', is_principal=True)

        self.bodeguero = User.objects.create_user('bodeguero1', password='clave12345')
        self.bodeguero.groups.add(grupo_bodeguero)
        PerfilEmpleado.objects.create(usuario=self.bodeguero, bodega_asignada=self.bodega)

        self.categoria = Categoria.objects.create(nombre='Ferretería', prefijo='FER')
        self.material = Material.objects.create(categoria=self.categoria, nombre='Guante de cuero')
        StockBodega.objects.create(material=self.material, bodega=self.bodega, cantidad=10)

        self.trabajador_activo = Trabajador.objects.create(
            nombres='Juan', apellidos='Pérez', documento_identidad='0102030405', estado='ACTIVO'
        )
        self.trabajador_inactivo = Trabajador.objects.create(
            nombres='Carlos', apellidos='Ruiz', documento_identidad='0203040506', estado='INACTIVO'
        )

        self.client = Client()
        self.client.force_login(self.bodeguero)
        self.url = reverse('entrega_directa_bodeguero')

    def test_entrega_directa_requiere_trabajador_activo(self):
        resp = self.client.post(self.url, {
            'material_id': self.material.id,
            'trabajador_id': self.trabajador_inactivo.id,
            'cantidad': '2',
            'observaciones': 'Entrega de prueba',
        })
        self.assertEqual(resp.status_code, 404)  # get_object_or_404 con estado=ACTIVO
        self.assertEqual(EntregaDirecta.objects.count(), 0)

    def test_entrega_directa_exitosa_descuenta_stock_y_registra_justificativo(self):
        resp = self.client.post(self.url, {
            'material_id': self.material.id,
            'trabajador_id': self.trabajador_activo.id,
            'cantidad': '3',
            'observaciones': 'Se entrega para trabajo en obra Norte',
        }, follow=True)

        stock = StockBodega.objects.get(material=self.material, bodega=self.bodega)
        self.assertEqual(stock.cantidad, Decimal('7.00'))

        entrega = EntregaDirecta.objects.get()
        self.assertEqual(entrega.trabajador, self.trabajador_activo)
        self.assertEqual(entrega.justificativo, 'Se entrega para trabajo en obra Norte')
        self.assertEqual(entrega.movimiento.cantidad, Decimal('3.00'))
        self.assertEqual(entrega.movimiento.tipo, 'SALIDA')

    def test_entrega_directa_sin_justificativo_es_rechazada(self):
        resp = self.client.post(self.url, {
            'material_id': self.material.id,
            'trabajador_id': self.trabajador_activo.id,
            'cantidad': '1',
            'observaciones': '   ',
        }, follow=True)
        self.assertEqual(EntregaDirecta.objects.count(), 0)
        stock = StockBodega.objects.get(material=self.material, bodega=self.bodega)
        self.assertEqual(stock.cantidad, Decimal('10.00'))


class PrestamoDevolucionTestCase(TestCase):
    def setUp(self):
        self.bodega = Bodega.objects.create(nombre='Bodega Central', is_principal=True)
        self.usuario = User.objects.create_user('bodeguero1', password='clave12345')
        self.categoria = Categoria.objects.create(nombre='Herramientas', prefijo='HER')
        self.material = Material.objects.create(categoria=self.categoria, nombre='Taladro')
        StockBodega.objects.create(material=self.material, bodega=self.bodega, cantidad=5)
        self.trabajador = Trabajador.objects.create(
            nombres='Ana', apellidos='Torres', documento_identidad='1122334455', estado='ACTIVO'
        )

    def test_prestamo_descuenta_stock_y_devolucion_lo_restaura(self):
        movimiento = None
        stock_antes = StockBodega.objects.get(material=self.material, bodega=self.bodega).cantidad
        prestamo = PrestamoHerramienta.objects.create(
            trabajador=self.trabajador, material=self.material, bodega_origen=self.bodega,
            cantidad=Decimal('1.00'), entregado_por=self.usuario,
        )
        # Simulamos el descuento manual que hace la vista crear_prestamo
        stock = StockBodega.objects.get(material=self.material, bodega=self.bodega)
        stock.cantidad -= Decimal('1.00')
        stock.save()

        self.assertEqual(StockBodega.objects.get(material=self.material, bodega=self.bodega).cantidad, stock_antes - 1)

        prestamo.registrar_devolucion(usuario=self.usuario, condicion='BUEN_ESTADO', observaciones='Todo OK')
        prestamo.refresh_from_db()
        self.assertEqual(prestamo.estado, 'DEVUELTO')
        self.assertEqual(StockBodega.objects.get(material=self.material, bodega=self.bodega).cantidad, stock_antes)

    def test_no_permite_devolver_dos_veces(self):
        prestamo = PrestamoHerramienta.objects.create(
            trabajador=self.trabajador, material=self.material, bodega_origen=self.bodega,
            cantidad=Decimal('1.00'), entregado_por=self.usuario,
        )
        prestamo.registrar_devolucion(usuario=self.usuario, condicion='BUEN_ESTADO')
        with self.assertRaises(ValueError):
            prestamo.registrar_devolucion(usuario=self.usuario, condicion='BUEN_ESTADO')


class TrabajadorCicloDeVidaTestCase(TestCase):
    def setUp(self):
        self.trabajador = Trabajador.objects.create(
            nombres='Luis', apellidos='Mora', documento_identidad='9988776655', estado='ACTIVO'
        )

    def test_desactivar_y_reactivar_conserva_historial(self):
        self.trabajador.desactivar(motivo='Fin de contrato de obra')
        self.trabajador.refresh_from_db()
        self.assertEqual(self.trabajador.estado, 'INACTIVO')
        self.assertIsNotNone(self.trabajador.fecha_salida)
        self.assertEqual(self.trabajador.motivo_salida, 'Fin de contrato de obra')

        # Sigue existiendo en la base y es consultable como "anterior"
        self.assertTrue(Trabajador.objects.filter(id=self.trabajador.id, estado='INACTIVO').exists())

        self.trabajador.reactivar()
        self.trabajador.refresh_from_db()
        self.assertEqual(self.trabajador.estado, 'ACTIVO')
        self.assertIsNone(self.trabajador.fecha_salida)

        # El historial (versiones de simple_history) sigue existiendo
        self.assertGreaterEqual(self.trabajador.history.count(), 3)  # creado, desactivado, reactivado

    def test_no_permite_desactivar_dos_veces(self):
        self.trabajador.desactivar(motivo='Motivo cualquiera')
        with self.assertRaises(ValueError):
            self.trabajador.desactivar(motivo='Otro motivo')


class SalarioYPagoTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin1', password='clave12345', is_superuser=True, is_staff=True)
        self.trabajador = Trabajador.objects.create(
            nombres='Pedro', apellidos='Salas', documento_identidad='1231231234', estado='ACTIVO'
        )

    def test_cambio_de_salario_no_afecta_pagos_anteriores(self):
        self.trabajador.asignar_salario(monto=Decimal('500.00'), fecha_inicio_vigencia=date(2026, 1, 1), usuario=self.admin)

        pago_enero = self.trabajador.registrar_pago(
            periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 1, 31),
            fecha_pago=date(2026, 1, 31), usuario=self.admin,
        )
        self.assertEqual(pago_enero.salario_base, Decimal('500.00'))

        # Cambia el salario a partir de febrero
        self.trabajador.asignar_salario(monto=Decimal('600.00'), fecha_inicio_vigencia=date(2026, 2, 1), usuario=self.admin)

        pago_febrero = self.trabajador.registrar_pago(
            periodo_inicio=date(2026, 2, 1), periodo_fin=date(2026, 2, 28),
            fecha_pago=date(2026, 2, 28), usuario=self.admin,
        )
        self.assertEqual(pago_febrero.salario_base, Decimal('600.00'))

        # El pago de enero sigue mostrando el salario que tenía en su momento
        pago_enero.refresh_from_db()
        self.assertEqual(pago_enero.salario_base, Decimal('500.00'))

    def test_pago_con_horas_extra_y_descuentos_desglosa_correctamente(self):
        self.trabajador.asignar_salario(monto=Decimal('500.00'), fecha_inicio_vigencia=date(2026, 1, 1), usuario=self.admin)

        he = HoraExtra.objects.create(
            trabajador=self.trabajador, fecha=date(2026, 1, 10), tipo='ORDINARIA',
            cantidad_horas=Decimal('3.00'), valor_calculado=Decimal('30.00'), registrado_por=self.admin,
        )
        desc = Descuento.objects.create(
            trabajador=self.trabajador, motivo='Atraso', monto=Decimal('10.00'),
            fecha=date(2026, 1, 15), registrado_por=self.admin,
        )

        pago = self.trabajador.registrar_pago(
            periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 1, 31), fecha_pago=date(2026, 1, 31),
            usuario=self.admin, horas_extra_ids=[he.id], descuento_ids=[desc.id],
        )

        self.assertEqual(pago.salario_base, Decimal('500.00'))
        self.assertEqual(pago.total_horas_extras, Decimal('30.00'))
        self.assertEqual(pago.total_descuentos, Decimal('10.00'))
        self.assertEqual(pago.total_pagado, Decimal('520.00'))

        he.refresh_from_db()
        desc.refresh_from_db()
        self.assertEqual(he.pago, pago)
        self.assertEqual(desc.pago, pago)

    def test_no_permite_duplicar_pago_del_mismo_periodo(self):
        self.trabajador.asignar_salario(monto=Decimal('500.00'), fecha_inicio_vigencia=date(2026, 1, 1), usuario=self.admin)
        self.trabajador.registrar_pago(
            periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 1, 31),
            fecha_pago=date(2026, 1, 31), usuario=self.admin,
        )
        with self.assertRaises(ValueError):
            self.trabajador.registrar_pago(
                periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 1, 31),
                fecha_pago=date(2026, 1, 31), usuario=self.admin,
            )

    def test_no_permite_pago_sin_salario_asignado(self):
        with self.assertRaises(ValueError):
            self.trabajador.registrar_pago(
                periodo_inicio=date(2026, 1, 1), periodo_fin=date(2026, 1, 31),
                fecha_pago=date(2026, 1, 31), usuario=self.admin,
            )


class PaginasNuevasSmokeTestCase(TestCase):
    """Golpea cada pantalla nueva como Administrador para detectar errores de template."""

    def setUp(self):
        self.admin = User.objects.create_user('admin1', password='clave12345', is_superuser=True, is_staff=True)
        self.bodega = Bodega.objects.create(nombre='Bodega Central', is_principal=True)
        PerfilEmpleado.objects.create(usuario=self.admin, bodega_asignada=self.bodega)

        self.trabajador = Trabajador.objects.create(
            nombres='Sofia', apellidos='León', documento_identidad='5566778899', estado='ACTIVO'
        )
        self.trabajador.asignar_salario(monto=Decimal('400.00'), fecha_inicio_vigencia=date(2026, 1, 1), usuario=self.admin)

        self.categoria = Categoria.objects.create(nombre='Ferretería', prefijo='FER')
        self.material = Material.objects.create(categoria=self.categoria, nombre='Martillo')
        StockBodega.objects.create(material=self.material, bodega=self.bodega, cantidad=5)

        self.client = Client()
        self.client.force_login(self.admin)

    def test_paginas_cargan_sin_error(self):
        urls = [
            reverse('listar_trabajadores'),
            reverse('crear_trabajador'),
            reverse('editar_trabajador', args=[self.trabajador.id]),
            reverse('desactivar_trabajador', args=[self.trabajador.id]),
            reverse('ficha_trabajador', args=[self.trabajador.id]),
            reverse('listar_prestamos'),
            reverse('crear_prestamo'),
            reverse('entrega_directa_bodeguero'),
            reverse('configuracion_erp'),
            reverse('historial_movimientos'),
        ]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"{url} devolvió {resp.status_code}")

    def test_auditoria_renderiza_entrega_directa_y_prestamo(self):
        movimiento = MovimientoInventario.objects.create(
            material=self.material, tipo='SALIDA', cantidad=Decimal('1.00'),
            bodega_origen=self.bodega, responsable=self.admin,
            observaciones=f"[ENTREGA DIRECTA] Para {self.trabajador.nombre_completo} | prueba"
        )
        EntregaDirecta.objects.create(movimiento=movimiento, trabajador=self.trabajador, justificativo='Motivo de prueba')

        prestamo = PrestamoHerramienta.objects.create(
            trabajador=self.trabajador, material=self.material, bodega_origen=self.bodega,
            cantidad=Decimal('1.00'), entregado_por=self.admin,
        )
        prestamo.registrar_devolucion(usuario=self.admin, condicion='BUEN_ESTADO')

        resp = self.client.get(reverse('historial_movimientos'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Motivo de prueba')
        self.assertContains(resp, self.trabajador.nombre_completo)


class FormulaHorasExtraTestCase(TestCase):
    """
    Valida la fórmula de horas extra contra los valores reales del Excel de
    nómina de la empresa (Rol de Pagos RUC KM, fila de Luis Alfonso Aponte
    Caicedo: sueldo 550, 2h ordinaria -> 6.875, 8h extraordinaria -> 36.67).
    """

    def setUp(self):
        self.admin = User.objects.create_user('admin1', password='clave12345', is_superuser=True, is_staff=True)
        self.trabajador = Trabajador.objects.create(
            nombres='Luis Alfonso', apellidos='Aponte Caicedo', documento_identidad='1717003592', estado='ACTIVO'
        )
        self.trabajador.asignar_salario(monto=Decimal('550.00'), fecha_inicio_vigencia=date(2026, 1, 1), usuario=self.admin)

    def test_valor_hora_es_sueldo_sobre_240(self):
        valor_hora = servicios_nomina.calcular_valor_hora(self.trabajador)
        self.assertEqual(valor_hora, (Decimal('550.00') / Decimal('240')).quantize(Decimal('0.0001')))

    def test_hora_ordinaria_recargo_50_porciento(self):
        valor = servicios_nomina.calcular_valor_hora_extra(self.trabajador, 'ORDINARIA', Decimal('2'))
        self.assertEqual(valor, Decimal('6.88'))  # Excel: 6.875 (redondeo estándar a 2 decimales)

    def test_hora_extraordinaria_recargo_100_porciento(self):
        valor = servicios_nomina.calcular_valor_hora_extra(self.trabajador, 'EXTRAORDINARIA', Decimal('8'))
        self.assertEqual(valor, Decimal('36.67'))  # Excel: 36.666...

    def test_sin_salario_asignado_lanza_error_claro(self):
        trabajador_sin_salario = Trabajador.objects.create(
            nombres='Sin', apellidos='Salario', documento_identidad='0000000001', estado='ACTIVO'
        )
        with self.assertRaises(ValueError):
            servicios_nomina.calcular_valor_hora_extra(trabajador_sin_salario, 'ORDINARIA', Decimal('1'))

    def test_registrar_hora_extra_via_vista_calcula_valor(self):
        client = Client()
        client.force_login(self.admin)
        resp = client.post(
            reverse('registrar_hora_extra', args=[self.trabajador.id]),
            {'fecha': '2026-01-10', 'tipo': 'ORDINARIA', 'cantidad_horas': '2', 'observaciones': ''},
            follow=True,
        )
        hora = HoraExtra.objects.get(trabajador=self.trabajador)
        self.assertEqual(hora.valor_calculado, Decimal('6.88'))


class PagoQuincenalRealDelExcelTestCase(TestCase):
    """
    Reproduce exactamente la fila de Jonathan Stalyn Licto Cuchipe en el
    Excel real (sueldo 600, 1ra quincena de agosto):
      - HE Ordinaria (50%): 1h, HE Extraordinaria (100%): 8h
      - Bonificación del mes: 50, Aporte IESS del mes: 45.549
      - Días laborados en la quincena: 15
    Excel: AB5 = 300 + 3.75 + 40 + 25 - 0 - 0 - 22.7745 = 345.9755
    (el sistema redondea a centavos: 345.98)
    """

    def setUp(self):
        self.admin = User.objects.create_user('admin1', password='clave12345', is_superuser=True, is_staff=True)
        self.trabajador = Trabajador.objects.create(
            nombres='Jonathan Stalyn', apellidos='Licto Cuchipe', documento_identidad='0550058309',
            estado='ACTIVO', periodicidad_pago='QUINCENAL',
        )
        self.trabajador.asignar_salario(monto=Decimal('600.00'), fecha_inicio_vigencia=date(2026, 8, 1), usuario=self.admin)

    def test_pago_primera_quincena_coincide_con_excel(self):
        periodo_mensual = PeriodoNominaMensual.objects.create(
            trabajador=self.trabajador, anio=2026, mes=8,
            bonificacion=Decimal('50.00'), aporte_iess=Decimal('45.549'), registrado_por=self.admin,
        )
        self.assertEqual(periodo_mensual.bonificacion_quincenal, Decimal('25.00'))
        self.assertEqual(periodo_mensual.aporte_iess_quincenal, Decimal('22.77'))  # 45.549/2 = 22.7745 -> 22.77

        he_ordinaria = HoraExtra.objects.create(
            trabajador=self.trabajador, fecha=date(2026, 8, 14), tipo='ORDINARIA',
            cantidad_horas=Decimal('1'), registrado_por=self.admin,
        )
        he_ordinaria.valor_calculado = servicios_nomina.calcular_valor_hora_extra(self.trabajador, 'ORDINARIA', Decimal('1'))
        he_ordinaria.save()
        self.assertEqual(he_ordinaria.valor_calculado, Decimal('3.75'))  # Excel: M5=3.75

        he_extraordinaria = HoraExtra.objects.create(
            trabajador=self.trabajador, fecha=date(2026, 8, 12), tipo='EXTRAORDINARIA',
            cantidad_horas=Decimal('8'), registrado_por=self.admin, observaciones='Horas laboradas en feriado',
        )
        he_extraordinaria.valor_calculado = servicios_nomina.calcular_valor_hora_extra(self.trabajador, 'EXTRAORDINARIA', Decimal('8'))
        he_extraordinaria.save()
        self.assertEqual(he_extraordinaria.valor_calculado, Decimal('40.00'))  # Excel: N5=40

        pago = self.trabajador.registrar_pago(
            periodo_inicio=date(2026, 8, 1), periodo_fin=date(2026, 8, 15), fecha_pago=date(2026, 8, 15),
            usuario=self.admin, dias_laborados=Decimal('15'),
            horas_extra_ids=[he_ordinaria.id, he_extraordinaria.id],
            periodo_mensual=periodo_mensual,
        )

        self.assertEqual(pago.salario_base, Decimal('300.00'))  # Excel: AA5 = 20 (valor día) * 15 = 300
        self.assertEqual(pago.total_horas_extras, Decimal('43.75'))  # 3.75 + 40
        self.assertEqual(pago.bonificacion, Decimal('25.00'))
        self.assertEqual(pago.aporte_iess, Decimal('22.77'))
        self.assertEqual(pago.total_pagado, Decimal('345.98'))  # Excel (sin redondeo): 345.9755
